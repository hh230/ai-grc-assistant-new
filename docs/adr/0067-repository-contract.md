# ADR 0067 — Repository Contract

The transaction boundaries, fixed **before** any repository code exists. Every race condition
found in this project so far was created by writing the repository first and discovering the
boundary afterwards.

No implementation, no SQL, no classes. If this contract needs to change once implementation
starts, the design was not ready.

**Reading the columns.** *Cardinality* is rows touched per call at realistic scale.
*Isolation* / *Lock* / *Retry* are **binding**, not suggestions: concurrency behaviour must never
be an implicit consequence of how someone happened to write the SQL. *Idempotent* means calling
twice with identical arguments leaves the same state and raises nothing the caller must handle.

Everything is `READ COMMITTED` — PostgreSQL's default — except one read. Where a stronger
guarantee is needed it comes from a **lock or a guarded write**, not from raising the isolation
level, because isolation escalation buys serialization failures that every caller then has to
handle.

## Knowledge side — `knowledge_approver` operations

| Method | SQL touches | Cardinality | Transaction | Isolation | Lock | Retry | Idempotent? |
|---|---|---|---|---|---|---|---|
| `register_industry` | `industries` W | 1 | single stmt | READ COMMITTED | none | no | **yes** — `ON CONFLICT DO NOTHING` |
| `list_industries` | `industries` R | ≤ 100s | none | READ COMMITTED | none | no | yes (read) |
| `ensure_template` | `knowledge_templates` W | 1 | single stmt | READ COMMITTED | none | no | **yes** — `ON CONFLICT DO NOTHING` + read back |
| `create_release` | `template_releases` W 1 · `release_questions` W 5–50 | 1 + N | **explicit** | READ COMMITTED | **`FOR UPDATE` on the parent `knowledge_templates` row** | **no** — see §1 | no — each call mints a version |
| `submit_for_review` | `template_releases` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE status='draft'` | no | **yes** — second call matches 0 rows |
| `approve_release` | `template_releases` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE status='in_review'` | no | **yes** |
| `mark_released` | `template_releases` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE status='approved'` | no | **yes** |
| `activate_release` | `active_templates` W 1 · `active_template_history` W 1 | 2 | **explicit** | READ COMMITTED | **upsert row lock** (`ON CONFLICT … DO UPDATE`) — see §2 | no | no — every activation is a distinct event |
| `get_active_release` | `active_templates` R · `template_releases` R · `release_questions` R | 1 + 5–50 | none | READ COMMITTED | **none — never `FOR UPDATE`** | no | yes (read) |
| `list_activation_history` | `active_template_history` R | ≤ 100s | none | READ COMMITTED | none | no | yes (read) |
| `save_translation` | `question_translations` W | 1 | single stmt | READ COMMITTED | none — upsert on PK | no | **yes** |
| `publish_translation` | `question_translations` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE status='reviewed'` | no | **yes** |
| `retire_release` | `template_releases` W | 1 | single stmt | READ COMMITTED | none — guarded by source status | no | **yes** |

## Customer side — assessment operations

| Method | SQL touches | Cardinality | Transaction | Isolation | Lock | Retry | Idempotent? |
|---|---|---|---|---|---|---|---|
| `open_assessment` | `assessments` W | 1 | single stmt | READ COMMITTED | none | no — a duplicate id is a caller bug, surfaced | no — a new assessment is a new fact |
| `record_selection` | `template_selections` W | 1 | single stmt | READ COMMITTED | none — upsert on PK | no | **yes** |
| `save_sector_answers` | `sector_answers` W | 5–50 | **explicit** | READ COMMITTED | **none** — see §4 | no | **yes** — batch upsert on the composite PK |
| `load_plan_context` | `assessments` R · `template_selections` R · `sector_answers` R · `release_questions` R | 1 + 1 + 5–50 + 5–50 | **explicit, read-only** | **REPEATABLE READ** — see §3 | none | no | yes (read) |
| `complete_assessment` | `assessments` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE completed_at IS NULL` | no | **yes** |

## The four boundaries that exist for a reason

Numbered so the table can point at them.

### §1 `create_release` — version allocation, and why NO retry

`UNIQUE (template_id, version)` makes a collision impossible but not impossible to *hit*: two
generators both read `max(version)=3` and both write 4. `FOR UPDATE` on the parent
`knowledge_templates` row serialises allocation **for that industry only**, so real estate and
healthcare never wait on each other. The questions are written in the same transaction, because a
release with no questions is not a release.

**Retry is deliberately `no`, differing from the example that prompted this column.** With the
lock held, the read-then-write is atomic and a `UniqueViolation` is unreachable through this path.
If one occurs anyway it means the caller supplied an explicit duplicate version — a bug to
surface, not to paper over by trying again. A retry here would be dead code that hides the one
case it could ever fire on.

### §2 `activate_release` — an upsert lock, not `FOR UPDATE`

**Correction to the first draft of this contract**, found while filling in this column:
`SELECT … FOR UPDATE` cannot lock a row that does not exist, and the *first* activation for an
industry is exactly that case — two concurrent first activations would both see no row, both
insert, and one would fail on the primary key.

`INSERT … ON CONFLICT (industry_slug) DO UPDATE` takes the row lock itself and covers both the
first activation and every later one. Concurrent activations serialise on it, and both write their
own history row — which is correct: both genuinely happened, and the pointer ends at the later.

The pointer and the history are written in one transaction because, split apart, a crash between
them leaves either a pointer nobody can explain or a history entry for something that never took
effect.

### §3 reads — `get_active_release` takes no lock; `load_plan_context` takes a snapshot

`get_active_release` runs on **every interview**. `FOR UPDATE` here would serialise every customer
in a sector behind one row; MVCC already gives a consistent read without it. Stated explicitly
because it is precisely the "safety" a later reader adds by reflex.

`load_plan_context` is the one place `READ COMMITTED` is not enough. It composes **four** reads
into a single artifact that feeds the LLM and is then frozen into a plan; under `READ COMMITTED`
each statement sees its own snapshot, so a concurrent `save_sector_answers` could produce a
context whose answers and questions disagree. `REPEATABLE READ` gives all four reads one snapshot.
It costs nothing here and needs no retry, because a **read-only** transaction cannot raise a
serialization failure — the reason this is a snapshot rather than `SERIALIZABLE`.

### §4 `save_sector_answers` — all or nothing, and why no lock

Answers arrive as a set. Half of them persisted is an interview that cannot be interpreted, and
the plan context built from it would be silently incomplete rather than obviously broken — so the
batch is one transaction.

No lock: every row is keyed by `(assessment_id, release_id, question_id)` and one assessment is
answered by one interview, so there is no second writer to race. The upsert makes a repeated
submission harmless.

## What the contract deliberately does not give the repository

- **No delete of anything.** Knowledge Freeze (§7) and §8 are enforced in the schema; the
  repository exposes no method that could attempt one, so a caller cannot even ask.
- **No update of released content.** `retire_release` moves status only. There is no
  `update_release_questions`.
- **No lifecycle logic.** Guards are `WHERE` clauses on the current status; which transition is
  legal is the domain's decision, not the repository's.
- **No tenant defaulting.** Every customer-side method takes the tenant explicitly. A repository
  that infers a tenant is one bug away from crossing the boundary.
