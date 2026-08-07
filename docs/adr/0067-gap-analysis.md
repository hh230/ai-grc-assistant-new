# ADR 0067 — Gap Analysis: prototype code vs. the accepted decision

**Date:** 2026-08-07 · **Purpose:** decide the minimum that must change *before* migrations.

**The decisive fact:** `governance_discovery/knowledge_template.py` is imported by nothing except
its own tests. It is not exported from the package, not referenced by `grc-api`, and reachable
from no running code path. Its blast radius is zero, so no difference in it can produce a wrong
migration — the migration is written from the ADR, not from these dataclasses.

## Verdict

| category | count |
|---|---|
| **Must Fix Before Migration** | **0** |
| Can Be Deferred | 7 |
| Cosmetic | 2 |

**Nothing needs to change before step 1.** Migrations are written from ADR 0067's data-model
section; the prototype does not constrain them.

## Every difference, classified

| # | difference | prototype | ADR 0067 | class | why |
|---|---|---|---|---|---|
| 1 | template shape | one `KnowledgeTemplate` holding version + questions + status | container + `TemplateRelease` per version | **Deferred** | The schema is written from the ADR. This bites at the **store/codec** (step 3), where a lying mapping would be written — fix it then, with the table in front of us. |
| 2 | activation | `published_at` + `PUBLISHED` status | `active_templates` pointer row | **Deferred** | Same: no code reads it. Becomes Must-Fix at step 3. |
| 3 | `suggest_template` | filters by `is_usable` (status) | reads the active pointer | **Deferred** | Only called by tests. Becomes wrong at step 4 (API), not before. |
| 4 | lifecycle states | 5 (`generated…deprecated`) | 6 + `superseded` | **Deferred** | Status is a `text` column with a CHECK constraint in the migration; the constraint is authored from the ADR. The enum catches up when the store lands. |
| 5 | selection binding | none (free-standing) | `assessment_id` | **Deferred** | `assessments` and `template_selections` are created correctly by the migration regardless. |
| 6 | selection identity | `selected_version_ids` as `"real_estate@v3"` strings | `selected_release_ids` | **Deferred**, and the highest-risk of these | If the column is `uuid[]` and the domain emits composite strings, the first store write fails. It fails **loudly at step 3**, not silently — and step 3 is where it gets fixed. |
| 7 | provenance | `generated_by`, `prompt_version` | + `generated_by_model`, `generator_commit` | **Deferred** | Columns exist from day one; the dataclass fills them when generation is wired (step 4). |
| 8 | `SectorAnswer.framework` | single string | should mirror `references` | **Cosmetic** | Denormalised label for display. Affects no key, no constraint. |
| 9 | `SectorAnswerSet` | `template_version_id` string | `release_id` | **Cosmetic** | Same value, different name; renamed when the store lands. |

## Why "Must Fix = 0" is the honest answer, not a dodge

I expected to find at least one blocker and looked specifically for these three:

- **Would the prototype pull the schema toward it?** Only if I wrote the migration from the
  dataclasses. I will write it from the ADR's data-model table, which already names all nine tables
  and their columns.
- **Would a wrong column type get baked in?** The one candidate is #6 (`selected_release_ids`).
  ADR 0067 specifies it; the prototype does not override it.
- **Would a constraint be missed?** The two that matter — `active_templates` keyed on
  `industry_slug`, and `language <> 'ar'` — come from the ADR, not the code.

None of them require touching a line today.

## The rule I will work by from now on

> **A change to existing code must prevent a concrete error in the next executable step.**
> "The design is cleaner" is not a reason. If the current shape does not block the next step,
> it waits until the step that actually touches it.

Applied here: every difference above is **real**, and every one of them is **cheaper to fix when
the code that consumes it exists**, because that code proves the fix is right. Fixing #1 today
means rewriting the domain twice — once from the ADR, once again when the store reveals what the
mapping actually needs.

Two consequences I accept knowingly:

- The prototype and the ADR will disagree in the repository for the length of steps 1–2. That is
  recorded here and in the ADR's status, so it reads as a decision rather than as drift.
- Items 1, 2, 3 and 6 are promoted to **Must Fix** the moment step 3 (store/codec) begins. They are
  not forgotten; they are scheduled.
