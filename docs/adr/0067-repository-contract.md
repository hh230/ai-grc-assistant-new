# ADR 0067 — Repository Contract

The transaction boundaries, fixed **before** any repository code exists. Every race condition
found in this project so far was created by writing the repository first and discovering the
boundary afterwards.

No implementation, no SQL, no classes. If this contract needs to change once implementation
starts, the design was not ready.

**Reading the columns.** *Cardinality* is rows touched per call at realistic scale.
*Transaction* says what the method must hold, not what it happens to do. *Idempotent* means
calling it twice with identical arguments leaves the same state and raises nothing the caller
must handle.

## Knowledge side — `knowledge_approver` operations

| Method | SQL touches | Expected cardinality | Required transaction | Idempotent? |
|---|---|---|---|---|
| `register_industry(slug, name_ar)` | `industries` W | 1 | single statement | **yes** — `ON CONFLICT (slug) DO NOTHING` |
| `list_industries(include_retired=False)` | `industries` R | ≤ 100s | none | yes (read) |
| `ensure_template(industry_slug)` | `knowledge_templates` W | 1 | single statement | **yes** — `ON CONFLICT (industry_slug) DO NOTHING`, then read back |
| `create_release(template_id, questions, provenance, created_by)` | `template_releases` W 1 · `release_questions` W 5–50 | 1 + N | **explicit txn, `SELECT … FOR UPDATE` on the parent `knowledge_templates` row** | **no** — each call mints a new version |
| `submit_for_review(release_id)` | `template_releases` W | 1 | single statement, guarded `WHERE status='draft'` | **yes** — a second call matches 0 rows |
| `approve_release(release_id, approver, at)` | `template_releases` W | 1 | single statement, guarded `WHERE status='in_review'` | **yes** — same guard |
| `mark_released(release_id, at)` | `template_releases` W | 1 | single statement, guarded `WHERE status='approved'` | **yes** |
| `activate_release(industry_slug, release_id, actor, reason)` | `active_templates` W 1 · `active_template_history` W 1 | 2 | **explicit txn, `FOR UPDATE` on the `active_templates` row** | **no** — every activation is a distinct historical event |
| `get_active_release(industry_slug)` | `active_templates` R · `template_releases` R · `release_questions` R | 1 + 5–50 | none — **never `FOR UPDATE`** | yes (read) |
| `list_activation_history(industry_slug)` | `active_template_history` R | ≤ 100s | none | yes (read) |
| `save_translation(release_id, question_id, language, text)` | `question_translations` W | 1 | single statement | **yes** — upsert on the composite PK |
| `publish_translation(release_id, question_id, language)` | `question_translations` W | 1 | single statement, guarded `WHERE status='reviewed'` | **yes** |
| `retire_release(release_id, target_status)` | `template_releases` W | 1 | single statement | **yes** — guarded by the source status |

## Customer side — assessment operations

| Method | SQL touches | Expected cardinality | Required transaction | Idempotent? |
|---|---|---|---|---|
| `open_assessment(tenant, organization_id, source_session_id=None)` | `assessments` W | 1 | single statement | **no** — a new assessment is a new fact; the caller supplies the id |
| `record_selection(assessment_id, suggested, release_ids, by)` | `template_selections` W | 1 | single statement | **yes** — upsert on `assessment_id` (PK), until the interview starts |
| `save_sector_answers(assessment_id, answers)` | `sector_answers` W | 5–50 | **explicit txn** — a half-saved answer set is not a valid interview | **yes** — batch upsert on the composite PK |
| `load_plan_context(assessment_id)` | `assessments` R · `template_selections` R · `sector_answers` R · `release_questions` R | 1 + 1 + 5–50 + 5–50 | none | yes (read) |
| `complete_assessment(assessment_id, at)` | `assessments` W | 1 | single statement, guarded `WHERE completed_at IS NULL` | **yes** — a second call matches 0 rows |

## The four boundaries that exist for a reason

**`create_release` — version allocation.** `UNIQUE (template_id, version)` makes a collision
impossible but not impossible to *hit*: two generators both read `max(version)=3` and both write
4, and one fails. The lock on the parent `knowledge_templates` row serialises allocation for that
industry only, so real estate and healthcare never wait on each other. The questions are written
in the same transaction because a release with no questions is not a release.

**`activate_release` — the pointer and its history must agree.** Written separately, a crash
between them leaves either a pointer nobody can explain or a history entry that never took effect.
`FOR UPDATE` also turns two simultaneous activations into a queue rather than a silent
last-writer-wins, which matters because both would otherwise appear in the history as if both had
been live.

**`get_active_release` — deliberately no lock.** It runs on every interview. Taking `FOR UPDATE`
here would serialise every customer in a sector behind one row; MVCC already gives a consistent
read without it. Stated explicitly because it is exactly the kind of "safety" someone adds later
by reflex.

**`save_sector_answers` — all or nothing.** Answers arrive as a set. Half of them persisted is an
interview that cannot be interpreted, and the plan context built from it would be silently
incomplete rather than obviously broken.

## What the contract deliberately does not give the repository

- **No delete of anything.** Knowledge Freeze (§7) and §8 are enforced in the schema; the
  repository exposes no method that could attempt one, so a caller cannot even ask.
- **No update of released content.** `retire_release` moves status only. There is no
  `update_release_questions`.
- **No lifecycle logic.** Guards are `WHERE` clauses on the current status; which transition is
  legal is the domain's decision, not the repository's.
- **No tenant defaulting.** Every customer-side method takes the tenant explicitly. A repository
  that infers a tenant is one bug away from crossing the boundary.
