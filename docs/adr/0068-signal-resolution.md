# ADR 0068: Signal Resolution — how a sector answer reaches the decision engine

- **Status: Accepted** — 2026-08-09, after two rounds of owner review. Seven amendments were
  required before approval and are all applied: the unified `option_id`-keyed `signal_value_map`,
  provenance separated from the resolved value, idempotence corrected to "the FUNCTION is
  idempotent, the conclusion is one-way", a historical backfill, and three additional tests
  (18, 22–24). Phase 1 — the channel — is implemented; no shipped pack declares anything yet.
- **Date:** 2026-08-09
- **Deciders:** Product owner; platform engineering
- **Related:** CLAUDE.md §3 (pillars 1, 2, 5, 8, 9), §6.16 (fail safe, not open), §19
  (transparency & reproducibility), §23 (ADRs); ADR 0066 (Governance Discovery & Planning),
  0067 (Sector Knowledge Packs — Knowledge Freeze, Assessment Freeze), 0044 (Human Approval),
  0045 (V2 persistence style)

## Context

The seven Sector Knowledge Packs (142 questions) do not reach the decision engine, and that was
deliberate: `test_sector_answers_change_NOTHING_the_rule_engine_decided` is green against a real
Postgres, and `draft_tool.py` says it in its own words — *"never mixed into it… only reach the
prompts that write PROSE"*.

Three measured facts argue for NARROWING that boundary rather than removing it:

1. **Absence dominates, not disagreement.** In real concluded sessions (14 — a small sample, so
   not generalised): `operates_critical_infrastructure` answered 3 times, `data_geography` 5,
   `ownership_type` 5; against 11 for `handles_personal_data`. In 270 synthetic harness sessions,
   the first three are answered zero times.
2. **The rules exist and are starved.** 40 rules and 10 derivations wait on `subject_to_nca` and
   `cross_border_data_exposure`; the sector packs ask exactly those facts (`re_nca_scope`,
   `re_cross_border_transfer`) and discard the answers.
3. **Measured duplication.** Six questions in `real_estate` alone (hand-verified) restate what
   `core.json` already asks. The customer answers twice and one answer reaches a decision.

## Decision

### D1 — A declared channel, with one declaration shape for every question type

A sector question may carry `writes_signal`, and only under all of:

**(a) Closed types only.** `enum` and `boolean`. `text` never. `multi_select` is DEFERRED — turning
a set-valued answer into a scalar needs a condition ("if any of these…"), and a condition inside a
knowledge pack is a rule, which the pack contract forbids.

**(b) Keyed by a stable `option_id`, never by text.** Boolean questions are not an exception: their
branches use the reserved ids `"true"` and `"false"`, so there is one mechanism rather than one per
type. Text is for humans; the decision path never reads it.

**(c) Exhaustive in both directions.** Every declared option has an entry; every entry names a real
option. A missing key is a validation failure, never a default.

**(d) Types and vocabulary checked** against the engine's own definition of the signal.

**(e) No inferential conversion.** No text matching, no keywords, no model.

**(f) Absence never becomes `False`.** An unanswered question, an option declared `null`, and a
boolean branch declared `null` all contribute nothing. "We don't know" is not "no". This is where
wrong compliance decisions come from, so it is closed by contract rather than by care.

**(g) Backward compatible.** `option_id` is required only where a declaration exists, so the seven
released packs — none of which declares anything — stay valid and untouched.

### D2 — Closed vocabulary, derived from the engine

`writes_signal` accepts only a signal an engine QUESTION writes and something READS. Of 30 signals:
six are orphans (`has_it_team`, `has_legal_team`, `held_licenses`, `last_policy_review_date`,
`additional_context_note`, `organization_language`), six are derived conclusions
(`subject_to_nca`, `subject_to_pdpl`, `subject_to_sama`, `is_government_linked`,
`provides_financial_services`, `cross_border_data_exposure`), and `primary_activity` selects the
sector. **17 remain.** The list is computed from the loaded packs (`writable_signals`), never
maintained by hand — a second list would be a second source of truth about the engine's own
vocabulary.

### D3 — Three outcomes, and no fourth

`ABSENT` fills · `AGREE` changes nothing and records corroboration · `DISAGREE` records a conflict.

### D4 — A conflict is data; the core value stands

Both answers come from the same customer at full confidence, and the sector question is not more
specific — only differently worded. So no winner is invented: the sector value is suppressed, the
plan is exactly what it would have been without this feature, and the conflict is surfaced to a
human at the approval gate.

### D5 — Two write points, one per event, and neither substitutes for the other

**v1 is written by the discovery conclusion**, in `DiscoverySessionService._advance`, where the
analysis is computed and inside the same transaction that concludes the session. If it cannot be
written the conclusion does not happen.

**v2 is written by the sector-assessment conclusion**, once, and it does NOT create a missing v1.
A first draft let it backfill one on demand; review rejected that, correctly — it made two write
paths for one fact and left every session without a sector interview with no version at all.
Historical sessions get their v1 from `grc_api.backfill_applicability`, not from a fallback.

### D6 — The value and its provenance are separate

`Signal` is unchanged. `resolve()` returns `(SignalSet, tuple[ResolvedSignal, ...])`. In the
CORROBORATED case `origin` stays `CORE_ANSWER` — the core interview remains the source and the
sector claim is recorded as corroboration, not as a second author of the same fact.

### D7 — No role for the model

Values are declared data; resolution is code. **The generator REFUSES `writes_signal` and
`signal_value_map`** (`_FORBIDDEN_FIELDS`), so a declaration is always a human's, reviewed as its
own change.

### D8 — The conclusion is one-way; idempotence is a property of the function

`resolve()` is idempotent. A concluded assessment is never re-concluded — `assessments_conclude_once`
refuses it, and `UNIQUE (tenant_id, assessment_id)` independently refuses its RESULT. Later reads
use the stored version and never recompute. Any future recomputation is a NEW explicit versioned
operation (`source='recomputation'`) with its own gate — reserved in the vocabulary, not built here.

### D9 — The historical backfill copies; it never computes

`grc_api.backfill_applicability` writes v1 for every concluded session from the stored
`discovery_sessions.applicability`, verbatim. Provenance is reconstructed from stored rows only —
`discovery_answers` is append-only, so a signal with an answer row was ANSWERED and one without was
DERIVED. A session with no stored applicability gets no version, and its plans keep
`source_applicability_id = NULL`: "not recorded" is a fact about the past, and filling it in would
be a lie with a timestamp.

## Determinism, commutativity, idempotence

The merge is a join on a flat lattice, so the properties are structural:

```
⊥ ⊔ v = v        v ⊔ v = v        v ⊔ w = ⊤  (v≠w)        ⊤ ⊔ x = ⊤
```

Folding the sector claims cannot depend on their order. The core answer is applied as a
DISTINGUISHED input, not as one more element of the fold:

```
resolved(K) = core(K)      when the core interview answered K
            = ⨆ sector(K)  when the sector claims agree
            = unset        when they disagree and core is silent   (the fail-safe)
```

**Binding implementation constraint:** the merge must not be a loop over `SignalSet.with_signal` —
that is last-write-wins, the exact property this ADR rules out.

## Schema

Four migrations, each doing one thing, and none editing a file that has already been applied:

| | |
|---|---|
| `0018_applicability_versions` | `session_applicability_versions`: append-only (trigger), `UNIQUE(tenant, session, version)`, partial `UNIQUE(tenant, assessment)`, and CHECKs binding `version = 1` to `core_conclusion` and `assessment_id` to `sector_conclusion` |
| `0019_release_question_signals` | `release_questions.writes_signal` / `signal_value_map`, with `CHECK (writes_signal IS NULL OR signal_value_map IS NOT NULL)` |
| `0020_plan_applicability_link` | `governance_plans.source_applicability_id`, nullable |
| `0021_applicability_referential_integrity` | the composite tenant-safe foreign keys, and the `UNIQUE (id, tenant_id)` keys they need |

Every ALTER against a table from migrations 1–3 is guarded by `to_regclass`, because the ADR 0067
knowledge fixture builds a database from migrations 4 and up where those tables do not exist.
`IF NOT EXISTS` does not help: it forgives a missing COLUMN, never a missing TABLE.

## Lifecycle

```
1  core conclusion    → applicability v1 [core_conclusion]
2  sector interview   → answers saved incrementally; no decision moves
3  sector conclusion  ← ONE transaction, once, forever
   SELECT … FOR UPDATE → refuse if already concluded
   → read answers + declarations → resolve → derive → analyze → INSERT the version
   → UPDATE assessments SET completed_at   ← LAST: the freeze engages here
4  plan generation    → reads the stored version; conflicts shown at the approval gate
```

## What implementation and review revealed

Four things found by a constraint or a review rather than by writing the code — the argument for
stating invariants declaratively (CLAUDE.md §3 pillar 9).

**Nothing wrote v1.** `CHECK ((version = 1) = (source = 'core_conclusion'))` refused the first
sector conclusion. The first fix was a fallback in the sector path; owner review rejected it as
symptom-treating and it was replaced by writing v1 where the analysis is computed (D5).

**Two references were unenforced.** `session_id` and `source_applicability_id` shipped as plain
text. Review found what that permits by doing it: deleting a session left an orphan version, and a
plan was pointed at a version id that had never existed — both accepted silently. 0021 makes both
composite, tenant-safe foreign keys, following `sector_answers` (0015).

**The backfill collided with the fix.** Once discovery conclusion writes v1 under its own id, a
session can already have one that the backfill would duplicate on `(tenant_id, session_id,
version)` while colliding with nothing on `id`. `ON CONFLICT (id) DO NOTHING` became
`ON CONFLICT DO NOTHING`; the narrow form would have crashed a production backfill halfway.

**ADR 0067 §2 had to be amended, not bypassed.** A green test asserted that `release_questions` may
hold no column that puts an LLM fact on the decision path, and named `writes_signal` explicitly.
The property is right; the boundary moved. It is now held at the AUTHOR — the generator refuses the
field, only a human may declare it, the vocabulary is closed, and no rule may live in a pack. The
test names the exception and asserts the columns exist, so it can no longer pass for the wrong
reason.

## Consequences

**Gained:** one narrow auditable channel; starved rules fed from where the customer already
answers; a decision history that survives a pack bump, a deploy and a restart.

**Paid:** a new table and three columns; a real transaction on the conclusion path; a new conflict
shape for the approval UI; `option_id` as an authoring burden.

**Deliberately refused:** ranking "most recent" or "most specific"; rules inside sector packs; new
signals; any role for the model; any default when a declaration is absent.

**Deferred gap:** `multi_select` — 18 of 142 questions, including the strongest qualifiers
(`re_activities_practiced`, `re_data_categories`). Wiring it needs a condition, i.e. a rule, so it
needs its own ADR deciding where such conditions may live.

**Recorded gaps from the consulting draft:** `ownership_type` is mandatory at priority 8 and
answered 5 of 16 — a coverage problem in the core interview, not a packs problem. `held_licenses`
is an orphan AND its vocabulary (`iso_certified | government_license | industry_specific_license |
none`) collapses CMA, SOCPA and the Saudi Council of Engineers into one value, so wiring it would
not carry the meaning anyway.
