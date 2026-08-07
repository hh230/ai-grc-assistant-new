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

**Everything is `READ COMMITTED`** — PostgreSQL's default, with no exceptions. Where a stronger
guarantee is needed it comes from a **lock, a guarded write, or immutable data** — never from
raising the isolation level, which only buys serialization failures every caller must then handle.

> **Needing a higher isolation level is a signal that the domain still permits writes it should
> not.** Fix the lifecycle, not the transaction.

That rule already changed this contract once: `load_plan_context` was specified as
`REPEATABLE READ` to stop a concurrent answer from producing a context whose questions and answers
disagree. The real defect was that answers could still arrive at all — see the domain rule below.

## Knowledge side — `knowledge_approver` operations

| Method | SQL touches | Cardinality | Transaction | Isolation | Lock | Retry | Idempotent? |
|---|---|---|---|---|---|---|---|
| `register_industry` | `industries` W | 1 | single stmt | READ COMMITTED | none | no | **yes** — `ON CONFLICT DO NOTHING` |
| `list_industries` | `industries` R | ≤ 100s | none | READ COMMITTED | none | no | yes (read) |
| `ensure_template` | `knowledge_templates` W | 1 | single stmt | READ COMMITTED | none | no | **yes** — `ON CONFLICT DO NOTHING` + read back |
| `create_release` | `template_releases` W 1 · `release_questions` W 5–50 | 1 + N | **explicit** | READ COMMITTED | **`FOR UPDATE` on the parent `knowledge_templates` row** | **no** — see §1 | no — each call mints a version |
| `list_releases` | `template_releases` R · `knowledge_templates` R · `release_questions` R | 1–50 | none | READ COMMITTED | none | no | yes (read) |
| `submit_for_review` | `template_releases` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE status='draft'` | no | **yes** — second call matches 0 rows |
| `reject_release` | `template_releases` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE status IN ('in_review','approved')` | no | **yes** |
| `approve_release` | `template_releases` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE status='in_review'` | no | **yes** |
| `mark_released` | `template_releases` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE status='approved'` | no | **yes** |
| `set_active_release` | `industries` R·lock 1 · `active_templates` W 1 · `active_template_history` W 0–1 | 2–3 | **explicit** | READ COMMITTED | **`FOR UPDATE` on the `industries` row** — see §2 | no | setting a release: no, each is a distinct event · clearing: **yes** |
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
| `load_plan_context` | `assessments` R · `template_selections` R · `sector_answers` R · `release_questions` R — **every one filtered by `tenant_id`**, see §4 | 1 + 1 + 5–50 + 5–50 | none | READ COMMITTED | none — **the data is frozen**, see §3 | no | yes (read) |
| `complete_assessment` | `assessments` W | 1 | single stmt | READ COMMITTED | none — guarded `WHERE tenant_id = … AND completed_at IS NULL` | no | **yes** |

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

### §2 `set_active_release` — one primitive, and the lock is on the industry

There is one question here — **what is the active release for this industry?** — and exactly two
permitted answers: a release, or none. So there is one primitive. `release_id=None` is not a
second operation called "deactivate"; it is the other permitted answer to the same question. Two
methods for one fact is how the two drift apart.

The lock is on `industries`, not on `active_templates`. `SELECT … FOR UPDATE` cannot lock a row
that does not exist, and the *first* activation for an industry is exactly that case; the industry
row is guaranteed to exist by the foreign key, so locking it serialises every change to this
pointer. That also makes the **return value exact**: the method reports the release that was live
before the call, read under the same lock, rather than a value a concurrent activation could have
moved underneath it. Activation is a reviewer action, so serialising per industry costs nothing.
`ON CONFLICT (industry_slug) DO UPDATE` stays — it is what makes insert-or-replace one statement.

The pointer and the history are written in one transaction because, split apart, a crash between
them leaves either a pointer nobody can explain or a history entry for something that never took
effect.

### §3 reads — `get_active_release` takes no lock; `load_plan_context` takes a snapshot

`get_active_release` runs on **every interview**. `FOR UPDATE` here would serialise every customer
in a sector behind one row; MVCC already gives a consistent read without it. Stated explicitly
because it is precisely the "safety" a later reader adds by reflex.

`load_plan_context` composes **four** reads into a single artifact that feeds the LLM and is then
frozen into a plan, so a torn read would be a plan built half on one state and half on another.

An earlier draft solved this with `REPEATABLE READ`. That was treating the symptom. It reads only
a **concluded** assessment, and a concluded assessment accepts no further writes (the domain rule
below), so there is nothing to tear: four `READ COMMITTED` statements over immutable rows return
exactly what one snapshot would.

This is stronger than a snapshot, not weaker. A snapshot would have made a concurrent write
*invisible* to this read while still letting it land — leaving a stored plan that disagrees with
the assessment it came from, and no error anywhere.

### §4 `save_sector_answers` — all or nothing, and why no lock

Answers arrive as a set. Half of them persisted is an interview that cannot be interpreted, and
the plan context built from it would be silently incomplete rather than obviously broken — so the
batch is one transaction.

No lock: every row is keyed by `(assessment_id, release_id, question_id)` and one assessment is
answered by one interview, so there is no second writer to race. The upsert makes a repeated
submission harmless.

## What implementation asked for, and what that meant

Implementation requested five methods beyond the original eighteen. Only one was a gap in the
contract; the other four were the Application Service layer announcing itself, which is exactly
what this exercise was meant to detect.

| requested | verdict | because |
|---|---|---|
| `reject_release` | **added** | a state transition. The machine had approve, release and retire; without reject, a reviewer who disagrees has no move that is not a workaround |
| `get_release` | folded into `list_releases` | not a new operation — the same query with a filter. Two methods here meant the repository was being shaped by the screens reading it, not by the data |
| `list_releases` | **added as a read primitive**, not a new concept | every repository has Get/List; the original table simply omitted it |
| `translation_coverage` | **rejected** | a derived projection. It belongs to a read model or a SQL view — a repository that computes has acquired a second job |
| `retire_industry` | **rejected** | coordination: retire the industry, retire its active release, mark it inactive. Needing several repository calls IS the definition of a Service |

The contract is 19 operations plus the Get/List primitive. The rule this establishes:

> **If something needs more than one repository call, it is not a new repository method.
> It is a Service.**

## The domain rule this contract rests on

> **No writes are permitted after an Assessment reaches `Concluded`.**

Not a convention: `save_sector_answers`, `record_selection` and any future write keyed to an
assessment are refused once `completed_at` is set. The interview is over; what it produced is
evidence, and evidence that can still change is not evidence.

Three things follow, and they are the reason this rule is worth more than an isolation level:

- `load_plan_context` needs no snapshot, because there is nothing to tear.
- A plan can always be rebuilt from its assessment and produce the identical result — which is
  what CLAUDE.md §19 requires and what an auditor will ask for.
- The conclusion becomes a real event with a before and an after, rather than a flag.

If a future requirement genuinely needs to change a concluded assessment, the answer is a **new
assessment** — the same shape ADR 0067 already uses for knowledge, where a released asset is
never edited but superseded.

## What the contract deliberately does not give the repository

- **No delete of anything.** Knowledge Freeze (§7) and §8 are enforced in the schema; the
  repository exposes no method that could attempt one, so a caller cannot even ask.
- **No update of released content.** `retire_release` moves status only. There is no
  `update_release_questions`.
- **No lifecycle logic.** Guards are `WHERE` clauses on the current status; which transition is
  legal is the domain's decision, not the repository's.
- **No tenant defaulting.** Every customer-side method takes the tenant explicitly. A repository
  that infers a tenant is one bug away from crossing the boundary.
- **No write to a concluded assessment.** Enforced in the schema, not only in these methods, so a
  future caller that bypasses the repository cannot bypass the rule either.

### §4 the tenant is in the `WHERE`, not in a check afterwards

Both assessment operations above once took an assessment id and nothing else. Every other operation
on that table carries `tenant_id`; those two took the id on trust, which over an API is a
cross-tenant hole in both directions — `load_plan_context` returns another customer's organisation
and every answer they gave, and `complete_assessment` is irreversible, so one call with a foreign id
freezes another tenant's interview for good.

The filter is in the `WHERE` clause rather than a comparison after the read. For the write, because
the row must never move at all. For the read, because a caller must find **nothing**: a missing
assessment and another tenant's assessment are deliberately indistinguishable, since replying "that
exists, but not for you" confirms the id, and an assessment id is a fact about another customer.

`load_plan_context` carries the tenant into all three of its reads rather than trusting the first.
The column is denormalised onto each table and nothing in the schema binds a child row's tenant to
its parent's, so "the assessment is mine" does not by itself prove "these answers are". Closing that
declaratively — a composite foreign key `(assessment_id, tenant_id) → assessments(id, tenant_id)`,
the same technique `(release_id, release_status)` already uses — alters existing tables and is
therefore proposed, not done.
