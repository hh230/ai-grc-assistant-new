# ADR 0066: Governance Discovery & Planning — the AI Governance Planning Engine

- Status: Accepted — **Phase 3 (Mission, LLM roles, Plan Execution, versioning, Production
  Hardening) and the Phase 4 Product Flow Simplification (unified Discovery → Report → Plan
  journey, the first real frontend wiring of the Mission bridge) closed 2026-08-03**, within their
  declared scope (Phase 5 — seed sector data beyond `core`/`technology`/`cloud_provider` — and the
  separately-tracked Wave 1 executor migration remain open — see "Revision history")
- Date: 2026-08-02
- Deciders: Product owner; platform engineering
- Related: CLAUDE.md §3, §6, §8, §9, §13, §15, §19, §23; ADR 0042 (Mission Engine), 0043 (Mission
  Store), 0044 (Human Approval Lifecycle), 0045 (V2 persistence style), 0046 (AI GRC Assistant /
  Capability & Mission Catalog), 0047 (Capability: Risk Assessment — capability-addition
  precedent), 0048 (Per-step tool selection), 0049 (Tool step result contract), 0050 (Framework
  Library — frameworks as data), 0051 (Inter-step context)

## Context

The product's "Missions" section (`apps/web/app/[locale]/(app)/missions/`) is today a flat,
read-only table of pipeline runs, backed by a thin legacy table (`policy_missions`) that is
disconnected from the real V2 Mission Engine (ADR 0042). It is not what the product needs it to
become: a **Governance Planning Engine** that determines, for a business owner who does not know
GRC terminology and cannot name a regulatory framework, what applies to their organization and
what they need to do about it — without ever presenting a framework picker.

Three capabilities this requires do not exist anywhere in the platform today, confirmed by
codebase audit:

1. **Organizational structure.** `Organization` (`packages/domain/grc_domain/tenancy/entities.py`)
   has only `id, name, region, status`. There is no sector, size, or structural-signal concept
   anywhere in the domain — only free-text `orgType`/`industry` captured once at org creation in
   `apps/web`, with no edit path afterward.
2. **Framework applicability.** The Framework Library (ADR 0050,
   `v2/packages/framework-library/`) models frameworks as pure data (`Framework/Control/
   Requirement/EvidenceExpectation`) but has zero concept of *which organization a framework
   applies to*. Nothing in V2 or the V3 knowledge foundation
   (`v3/docs/knowledge/CANONICAL-MODEL.md`) links a framework/control to a sector, size, or any
   organizational signal.
3. **A structured, trackable transformation plan.** No aggregate anywhere models a GRC
   improvement plan as trackable records (status, priority, rationale, timeframe) rather than
   prose.

The Mission Engine's `MissionStatus` lifecycle (`CREATED, PLANNED, EXECUTING, AWAITING_APPROVAL,
RESUMED, COMPLETED, FAILED, CANCELLED, ARCHIVED`) is a frozen, closed transition table (ADR 0042
§7) with no state for "mid-question-tree, waiting on the next interview answer." Even
`AWAITING_APPROVAL` is a narrow, purpose-built value object added by ADR 0044, not a general pause
primitive — there is no precedent, and no appetite, for adding a general conversational-pause
state to the frozen Core.

A real organization is rarely one thing: a company can be a technology company, a FinTech, a cloud
provider, an e-commerce operator, and an AI provider simultaneously, with remote staff, all at
once. A design that binds a session to a single `industry_id` loses most of that reality. Likewise,
a business's governance maturity is not binary, and its ability to execute a transformation plan
is not a constant — a 3-person firm and a 3,000-person enterprise cannot absorb the same weekly
task load. These three facts shape the decision below.

## Decision

We will build the **AI Governance Planning Engine** as three new, additive bounded contexts. None
of them modify the frozen Mission lifecycle, the Tool contract, the agent roster, or the Framework
Engine model (CLAUDE.md §23) — everything below is new code and new tables, following existing
patterns.

### 1. Organization Profiling

A new `organization_profiles` aggregate (one per tenant) holding structural facts accumulated over
time: the currently active Knowledge Packs, a derived size band (for display/grouping — the
authoritative fact is the numeric `employee_count` signal, see §2), a derived maturity level, and
the full current `Signal` snapshot. Kept separate from the identity/tenancy `Organization`
aggregate, which is unchanged.

### 2. Governance Discovery — a two-tier adaptive interview, outside the Mission Engine

A `DiscoverySession` conducts a chat-like, one-question-at-a-time interview. It is deliberately
**not** modeled as a Mission (see Alternatives) — it is pure, unit-testable domain logic with an
append-only `discovery_answers` audit log, evaluated in two tiers that run at different times:

- **Tier A — live routing.** After every answer, the engine recomputes which **Knowledge Packs**
  are active (see below), unions their questions with the always-active `core` pack, filters by
  each question's own `applicability_predicate` against the current `Signal` set, and computes the
  next eligible question. This is what makes the interview adaptive (skip-irrelevant, activate new
  packs, re-route on a corrected answer) — and it **never** produces or exposes a framework
  recommendation, maturity score, capacity score, or plan item. Nothing Tier A computes is
  rendered to the user beyond "the next question."
- **Tier B — one-shot holistic analysis.** Exactly once, when a session transitions
  `in_progress → concluded`, every rule contributed by every pack that is active in the *final*
  `Signal` set is evaluated once, in a single batch pass, producing `{frameworks[], maturity,
  capacity, gaps[], plan_seeds[]}`, written atomically to `discovery_sessions.applicability`.
  Analysis is never incremental and never partially visible during the interview — this is a hard
  product requirement, not an implementation detail.

Both tiers are **deterministic, declarative, data-driven rule evaluation** — never free-form LLM
control flow (CLAUDE.md §6 pillar 8, §19). The only LLM involvement is a schema-validated
free-text-to-signal normalizer, bounded to resolving one answer's value, never deciding routing,
inference, or scheduling. Frameworks referenced by `recommends_framework` effects always name an
existing `framework_id` from the Framework Library (ADR 0050) — this ADR does not introduce new
framework data, only the applicability layer that decides which existing framework applies to
whom.

#### 2.1 Knowledge Packs are composable, not exclusive

An organization is not one industry. A session activates **as many Knowledge Packs as apply,
simultaneously** — e.g. `core + technology + cloud_provider + ai_provider + remote_workforce` for
a SaaS company that also does AI inference and employs remote staff. There is no single
`industry_id` field anywhere in this design.

Each pack is a self-contained data document under `knowledge-packs/packs/<pack_id>.json`,
declaring its own **activation predicate** over the shared Signal vocabulary — the same
declarative predicate language used for question eligibility:

```
{ "pack_id": "pack:cloud_provider", "version": "1.0",
  "labels": {"en": "Cloud Provider", "ar": "مزوّد خدمات سحابية"},
  "activation_predicate": { "any": [
      {"signal": "provides_saas", "op": "eq", "value": true},
      {"signal": "provides_cloud_infrastructure", "op": "eq", "value": true} ] },
  "questions": [ /* gated further by each question's own applicability_predicate */ ],
  "rules":     [ /* recommends_framework / maturity_dimension_score / plan_seed effects */ ],
  "gaps":      [ /* flags_gap effects */ ] }
```

`core` is the one pack with no activation predicate — it is always active for every session and
carries the sector-agnostic baseline (employee count, board, policies, risk register, compliance
officer, legal/IT function presence, execution capacity — see §2.3). An initial question ("what is
your organization's primary activity?", a dropdown covering common company types, per the original
product brief) sets early signals that typically activate one or two packs immediately (e.g.
`primary_activity = technology` activates `pack:technology`); further answers can activate
additional packs at any point — `activation_predicate` is re-evaluated from the live Signal set on
every turn, exactly like question eligibility (§2.4), so a company that turns out to run an
e-commerce storefront activates `pack:e_commerce` mid-interview without restarting anything.

**Example pack catalog** (each independently authored/versioned; not an exhaustive or fixed list —
adding one is a data change, see §2.2): `core`, `technology`, `fintech`, `legal`, `healthcare`,
`retail`, `construction`, `government`, `remote_workforce`, `cloud_provider`, `e_commerce`,
`ai_provider`.

`discovery_sessions.active_pack_ids` stores the live set of currently-active packs (recomputed
every turn, persisted for resumability and audit); `discovery_sessions.pack_versions` pins the
exact version of every pack that contributed a question or rule during the session, so a session
is byte-for-byte reproducible even after a pack file is later updated (CLAUDE.md §19).

#### 2.2 Engine vs. Knowledge Pack — the extensibility contract

**Generic — the engine. One implementation. Never edited to add a pack:**
- The `Signal` type system and predicate evaluation semantics (§2.3) — a small interpreter over
  declarative data, not `eval`'d code.
- Pack **activation** evaluation (union of packs whose `activation_predicate` is true) and, within
  active packs, the Tier A next-question selection algorithm (eligibility filter +
  priority/information-gain ordering).
- The Tier B one-shot batch-evaluation algorithm: fire every rule from every active pack once;
  dedupe framework recommendations; aggregate maturity-dimension and execution-capacity scores;
  apply the termination/confidence formula.
- The **`core` pack**: sector-agnostic baseline questions/rules every organization answers
  regardless of which other packs activate (employee count, board, policies, risk register,
  compliance officer, legal/IT presence, execution capacity) — it ships with the engine because it
  is universal, but is still authored as ordinary pack data, not special-cased code.
- The shared signal-key vocabulary and its typed value model (§2.3, Appendix A).
- The Framework Library (ADR 0050) — packs *reference* existing `framework_id`s, they never define
  new ones.
- The **deterministic Scheduler** (§2.5) that turns capacity-agnostic `plan_seed`s into
  time-bucketed `PlanItem`s.
- The plan pillar taxonomy (Governance/Risk/Compliance/Policies/Organization/HR/Legal/Cyber
  Security/Operations/AI Governance).

**Knowledge Pack — one JSON document per pack. The *only* thing that changes to add coverage:**
questions (each gated by its own `applicability_predicate`, writing to a signal key from the
shared vocabulary), rules (`recommends_framework` / `maturity_dimension_score` /
`capacity_weight?` / `plan_seed` effects), and gap rules — plus the pack's own
`activation_predicate`. A pack may only: (a) add questions/rules that fire when its predicate is
satisfied, (b) write to signal keys already in the shared vocabulary or propose new ones for
review, (c) reference existing `framework_id`s. A pack may never: contain engine code, define a
new predicate operator, or invent a framework. Adding "aviation," "insurance," or "energy" later is
authoring **one new pack file**, validated against a JSON Schema in CI, and nothing else — the
engine's code surface does not grow with the number of packs covered, and multiple packs compose
automatically because activation and question/rule firing are set-union operations by
construction.

#### 2.3 Signals are typed, not just boolean

A `Signal` is `{key, value_type, value, confidence, source_answer_id}`, where `value_type` is one
of:

- **`boolean`** — a true binary fact (e.g. `has_gov_clients`).
- **`enum`** — a closed, *ordered* set of states, used for anything with real maturity gradation.
  The default process/policy-maturity scale (used unless a pack declares a custom enum) is
  `absent < verbal < documented_unapproved < approved < reviewed_periodically` — five ordered
  levels, not a yes/no. Example: "do you have an organizational structure?" answers with this
  scale, not `yes|no`. Ordering lets `maturity_dimension_score` effects weight partial credit
  (`documented_unapproved` scores higher than `absent`, lower than `approved`).
- **`numeric`** — a real number, not a pre-bucketed range. `employee_count` is captured as the
  actual number the user enters, never as `small|large`. Bands (e.g. for display) are *derived* by
  the engine from the numeric value via a lookup, never the other way around — this is what makes
  execution-capacity scoring (§2.5) proportional rather than coarse.
- **`date`** — e.g. last policy review date, license expiry — enables staleness/urgency inference.
- **`percentage`** — e.g. share of revenue from personal-data processing, share of remote
  workforce.
- **`evidence_backed`** — a provenance modifier: the underlying value (still one of the types
  above) was corroborated by an uploaded/ingested document rather than self-reported, and is
  stamped `confidence = 1.0` directly, bypassing the free-text LLM normalizer. This is exposed as
  its own answer type because it changes engine behavior (confidence handling, and a future hook
  for evidence corroboration against the platform's existing Evidence/RAG layer), even though the
  value it carries is still fundamentally boolean/enum/numeric underneath.

The predicate DSL (`{"all"/"any": [...]}`, `{"signal","op","value"}`) supports `eq`/`neq`/`in` for
`boolean`/`enum` and `gte`/`lte`/`between` for `numeric`/`percentage`/`date`, plus an implicit
ordinal comparison for `enum` values on the default maturity scale (so a rule can say "at least
`documented_unapproved`" without enumerating every qualifying value).

#### 2.4 Next-question selection (Tier A) and interview conclusion

At each turn: recompute active packs (§2.1) → union their questions with `core` → filter to
questions whose `applicability_predicate` is true against current signals and not yet answered →
order by `(pack activation order, question priority, information-gain)`, where information-gain is
a static count of how many rules across all currently-active packs reference that question's
signal key. Ask the top candidate. Answer edits write a new `discovery_answers` row at a later
`sequence` and trigger a full recomputation from live signals — no separate "reroute algorithm"
(unchanged from the original design).

**Conclusion** ("enough"): no remaining eligible question is above the "required" priority
threshold, every maturity dimension and the capacity dimension have at least one contributing
signal, and `confidence_score ≥ 0.8`. If the interview stalls early (sparse/contradictory
answers), it still concludes — Tier B flags `applicability.confidence = "low"` and seeds the plan's
first item as "confirm basic governance facts with a GRC advisor" rather than guessing (CLAUDE.md
§6 pillar 16, fail-safe).

#### 2.5 Execution-capacity-aware scheduling — plans are computed, not templated

`plan_seed` effects **do not** declare a fixed timeframe bucket. Each declares
`{pillar, title_key, rationale_key, urgency: critical|high|medium|low, effort_size:
trivial|small|medium|large, depends_on?: [other plan_seed ids]}` — what to do and how
urgent/heavy it is, not when. Timing is computed in two deterministic steps, both part of the
generic engine (not pack data):

1. **Execution-capacity score** (a core, pack-independent Tier B computation, alongside maturity):
   a weighted, deterministic function of `core` signals — `employee_count` (log-scaled, not
   banded), `has_legal_team`, `has_it_team`, `has_compliance_officer`, and a direct self-reported
   `execution_capacity` question (an ordered enum: e.g. "no dedicated budget/time" through
   "dedicated compliance budget and team"). The result is a small integer **capacity tier**
   (`micro | small | mid | large | enterprise`), each tier mapping to a fixed **per-period item
   budget** (how many critical/high items, and how many total items, a bucket may hold) — a 3-person
   firm's Week-1 budget might be 2 critical items; a 3,000-person enterprise's might be 12.
2. **Deterministic scheduler** (in the `PLAN_SYNTHESIS_TOOL`, §3): bin-packs every `plan_seed` into
   `week_1 → week_2 → month_1 → month_3 → month_6 → year_1` (§4: the report's six-period timeline)
   in urgency order, respecting `depends_on` (an item cannot be scheduled in an earlier or same
   bucket than something it depends on unless capacity allows both in the same bucket after the
   dependency), filling each bucket up to its capacity-tier budget before spilling into the next;
   anything that doesn't fit inside the six-month horizon lands in `year_1`, the uncapped final
   bucket. This is a plain, auditable bin-packing algorithm — never an LLM decision — so a small
   organization is never handed an 18-task week and a large one is never under-scheduled relative
   to what it fired.

`governance_plan_items` records the computed `timeframe_bucket` and `priority` (from `urgency`) as
before, plus `effort_size` and `depends_on_item_ids` for transparency into why the schedule looks
the way it does.

### 3. Governance Planning — produced by a new, real, approval-gated Mission

Once a session concludes, a new Capability `generate_governance_plan` (input: the concluded
session's id, passed as `inputs["request"]` — the same single opaque-string input key every
builtin Capability uses, carried over REST as `CreateMissionBody.scope`) opens a real Mission,
modeled directly on the Gap Assessment capability
(`v2/packages/assistant-runtime/assistant_runtime/builtin/gap_assessment.py`):

1. `resolve_applicability` → new tool `ORG_APPLICABILITY_TOOL`: a pure, tenant-scoped read of the
   already-computed `discovery_sessions.applicability` (Tier B output: frameworks, maturity,
   capacity, gaps, plan_seeds). The Mission never re-evaluates rules.
2. `gather_control_library` → existing `CONTROL_LIBRARY_TOOL`, scoped to the frameworks from step
   1 (ADR 0051 inter-step context).
3. `draft_plan` → new tool `PLAN_DRAFT_TOOL`: combines steps 1–2, computes each item's `due_at`
   from its `timeframe_bucket` (§3.1), and applies the bounded LLM prose-generation role (drafts
   the Executive Brief, a Business Impact sentence per gap, and rationale/objective/
   expected-outcome/risk-if-skipped per item — §4/§5.2 — never deciding structure, timing, or
   priority, all of which are already fixed by step 1). Returns the complete draft as structured
   data — nothing is persisted yet.
4. `finalize_plan` → new tool `PLAN_FINALIZE_TOOL`, **consequential** (`consequential=True`):
   persists step 3's draft as a new `GovernancePlan`/`PlanItem` set, applying §3.1's immutable-
   snapshot rule (supersede the tenant's current active plan, if any).

**Why a draft/finalize split, not one `synthesize_plan` step (revised from the initial sketch):**
the Mission Engine's approval gate (`mission_engine/engine.py`) pauses **before** dispatching a
consequential step, not after it runs — so if drafting and persisting were the same step, the
human would be approving blind, before any content exists to review. Splitting them means the
gate sits exactly where "human proposes, human decides" requires it: `draft_plan` produces the
reviewable content (CLAUDE.md §1, §7 rule 9), the approval gate is crossed only once that content
exists, and `finalize_plan` performs the one actual write, strictly after approval. All three new
tools follow the ADR 0048/0049 contract: registered by name in `tool_names.py`, returning the
shared `ToolStepResult`, with no capability-layer import of the tool package.

Once created, day-to-day plan tracking (mark done, revisit later) is a plain user action on a
`governance_plan_items` record — not itself Mission-governed.

#### 3.1 Governance Plans are immutable snapshots

**Principle (product review, pre-implementation): a `governance_plans` row, once created, is never
edited.** Every time a discovery session concludes and its plan is approved, `synthesize_plan`
**inserts a new plan** rather than updating the tenant's existing one. The previous plan (if any)
transitions `status: active → superseded` in the same transaction — never deleted, never rewritten
— and is stamped with `maturity_at_supersession` (the *current*, live maturity per §5.3's
`effective_signals()` formula, captured at the moment it stops being the active plan — the "final
score" that version reached before the next one began). `version` (integer, per tenant, starting
at 1) and `previous_plan_id` (nullable self-reference) give explicit, queryable lineage on top of
`status` alone, so a later "compare versions" view can walk the chain without inferring order from
timestamps.

This is the same discipline `discovery_answers` already applies at the answer level (append,
never overwrite) and `mission-store`'s `plan_versions` applies to a Mission's own plan (ADR 0043) —
applied here one level up, to the artifact itself. It is what makes "how has this organization
changed" a real, answerable product question later: `governance_plan_items` and
`governance_plan_events` (§5.7) stay permanently attached to the plan version that created them —
completing a task never migrates it to a newer plan, and starting a new plan version never touches
or re-parents an older one's items. Each version is a closed book; only a new version is ever
opened.

### Persistence

A new package, `v2/packages/governance-store/`, following the ADR 0045 style used by
`mission-store` (sync psycopg3, raw parameterized SQL, `schema.py` as the single source of truth
for DDL mirrored by idempotent hand-written `.sql` migrations, kept in lock-step by a parity
test):

- **`organization_profiles`** — `primary_pack_id` (display convenience), `active_packs` (jsonb
  array, the composable set), `size_band`/`maturity_level` (derived/display), `signals` (jsonb,
  the raw typed snapshot).
- **`discovery_sessions`** — `active_pack_ids` (jsonb array, live), `pack_versions` (jsonb map,
  pinned per pack for reproducibility), `signals`, `confidence_score`, `applicability` (jsonb,
  written once at conclusion).
- **`discovery_answers`** — append-only; `raw_answer` (jsonb, shape depends on the question's
  `value_type`), `resolved_signal_key/value`, provenance (`normalized_by`, LLM audit columns).
- **`governance_plans`** — `inferred_frameworks`, `maturity_baseline`, links to session + Mission,
  plus (§3.1) `version`, `previous_plan_id`, `maturity_at_supersession` — immutable snapshots, never
  updated after creation.
- **`governance_plan_items`** — `pillar, title, objective, expected_outcome, rationale,
  timeframe_bucket, priority, effort_size, depends_on_item_ids, status, source_signal_keys,
  source_framework_refs, risk_if_skipped, revisit_at`.

Every table is `tenant_id`-scoped with tenant-first indexes (CLAUDE.md §20).

### Frontend integration (Phase 2 addendum)

Building the interview UI required resolving a question ADR 0052 explicitly left open: *how* does
`apps/web` (the Next.js product frontend, at the repo root — distinct from `v2/apps/*`) reach a
`v2/apps/*` host at all. Before this feature, it never had — `apps/web` either talked to its own
Postgres directly (the legacy Missions/Organizations pages) or called a different, older Python
service (`apps/api`) for policy-intelligence. CLAUDE.md's stack rule ("the frontend never talks to
the database directly; it goes through the API") settles *which* of the two non-options is
correct, but not which host.

**Decision: wire `apps/web` to the existing `v2/apps/grc-api` host (ADR 0052), not to a new
`v2/apps/web`.** `grc-api` already exists, already wires `mission-engine`/`assistant-runtime`, and
already has the exact `IdentityProvider` seam (`grc_api/security.py`) this needs. A new router
(`grc_api/routers/discovery.py`) exposes `/v1/discovery/*`; `apps/web`'s Next.js API routes
(`app/api/discovery/*`) are thin server-side proxies (`lib/discovery/service.ts`), mirroring the
existing `lib/policyIntelligence/service.ts` proxy-to-FastAPI pattern exactly. This is scoped
narrowly to Governance Discovery — it does not resolve ADR 0052's broader "apps/web vs a new
v2/apps/web" question for the rest of the product, only demonstrates one concrete answer for this
feature.

**Interim identity bridge.** `apps/web` has already authenticated the human via its own session
(`getActor()`); `grc-api` needs a `TenantContext` for that request but has no shared user database
with `apps/web`. Rather than building real cross-service identity federation now, `apps/web`
asserts the already-authenticated identity to `grc-api` via a short-lived (60s), HMAC-signed token
(`ServiceAssertionIdentityProvider`, `grc_api/service_identity.py`; minted in
`lib/discovery/serviceToken.ts`) — a standard trusted-BFF pattern: the signing secret
(`GRC_API_SERVICE_SECRET`) and every minted token are server-only, the browser never sees either.
This is deliberately interim: `security.py`'s `IdentityProvider` Protocol exists specifically so a
real OIDC/SSO provider (CLAUDE.md §20) can replace this with **zero route change**, the same
seam-swap property the dev fixed-credential provider already relies on. Not a new architectural
decision so much as exercising an existing one for the first time.

### 4. Report Design (Phase 3 addendum) — a consulting deliverable, not a task list

Before building the Mission's synthesis step, the owner set the bar explicitly: the output should
read like a paid assessment from a top consultancy, not an internal to-do list. Two decisions
follow from that: **frameworks are never the headline**, and **structure/facts are deterministic,
narrative is a bounded LLM overlay on top of them** — nothing here changes §2's rule that the
engine decides, the LLM only writes.

**Final report structure** (ten sections, in this order):

1. **AI Executive Brief** — 2–4 sentences of consultative narrative, LLM-drafted but strictly
   grounded in the deterministic `Applicability` result (maturity scores, gaps, capacity) —
   e.g. identifying that the root constraint is accountability/decision rights rather than
   security tooling, when the scores say so. Never invents a finding; only frames the ones that
   already fired.
2. **Current Maturity** — stars **and** a label together (ADR review: "stars alone don't carry
   enough meaning"), across five report-facing dimensions: **Governance, Risk, Compliance, Cyber
   Security, Leadership & Accountability**. Implemented: `MATURITY_DIMENSIONS` in `analysis.py`;
   `policy` folded into `governance`, `operational` renamed `cyber`, `leadership` is new (fed by a
   new `has_board` question + `has_compliance_officer` + `execution_capacity`, see `core.json`).
   `stars_and_label(score)` maps the existing 0–10 score to a 0–5 star count with a paired label
   (`none|limited|initial|developing|established|optimized`) — one shared function, so the number
   and the word are never inconsistent with each other.
3. **Critical Gaps** — what is missing (the deterministic `flags_gap` findings, unchanged
   mechanism).
4. **Business Impact** — what that absence costs the business, one LLM-drafted sentence per gap,
   grounded in the gap + the signals that triggered it. Split from (3) on review: "Gap" (fact) and
   "Impact" (consequence) are different claims and read as a real consulting deliverable when kept
   separate, rather than one technical bullet.
5. **Quick Wins** — a filtered *view* of the scheduled plan (small/trivial effort, high/critical
   urgency, landing in `week_1`/`week_2`) — no new domain logic, a rendering-time filter over
   `plan_items` so the client sees they can start immediately rather than waiting on a long plan.
6. **Priority Roadmap** — the same scheduled items grouped by `priority` (Critical/High/Medium/Low)
   as an overview, before the time-based view.
7. **Timeline** — the six-period schedule: **Week 1, Week 2, Month 1, Month 3, Month 6, Year 1**.
   Implemented: `scheduler.BUCKET_ORDER` and `capacity.PER_PERIOD_BUDGET` both widened from the
   original five buckets (`week_1/day_30/day_60/day_90/long_term`) to these six; `year_1` is now
   the uncapped final bucket.
8. **Action Tasks** — the scheduled items as trackable cards (unchanged mechanism from §2.5/§3).
9. **Methodology & Standards** — the *only* place a framework is ever named. The default,
   client-facing surface (sections 1–8) never says "NIST" or "ISO 27001" — it says the business
   was "analyzed against the best practices that apply to it." This is progressive disclosure, not
   concealment: `inferred_frameworks` is unchanged, fully populated, and one click away — CLAUDE.md
   §19's transparency requirement is met by *availability*, not by being the first thing read.
10. **Governance Vision** — "if this plan is fully executed" projection: a *second*, hypothetical
    run of the exact same deterministic maturity-scoring pass (`_score_maturity` in `analysis.py`),
    over a "best case" `SignalSet` where every process/policy-maturity signal is upgraded to the
    top of its ordered scale and every named accountability boolean (`has_board`,
    `has_compliance_officer`, `has_legal_team`, `has_it_team`) is flipped to `True` — structural
    facts (sector, headcount, execution capacity) are deliberately left untouched, since completing
    a governance plan doesn't change what industry an org is in. Exposed as
    `Applicability.maturity_vision`, same shape as `maturity`. Still zero LLM involvement in the
    *numbers*; an LLM may draft illustrative "what this looks like in practice" bullets grounded in
    which pillars accumulated the most completed items, but never states a fabricated count (e.g.
    "12 policies") that wasn't actually measured.

**What Phase 3 (the Mission) still owns, not yet built:** the two new LLM roles (Executive Brief
synthesis; per-gap Business Impact drafting) as bounded prompts, `PLAN_SYNTHESIS_TOOL` assembling
all ten sections, and `governance_plans`/`governance_plan_items` schema additions
(`executive_summary text`, `top_risks jsonb`) to persist them. Sections 2, 3, 5, 6, 7, 8, 10's
*numbers* are already implemented and tested in `governance-discovery` — Phase 3 only adds
narrative on top of values that already exist.

### 5. Plan Execution & the Governance Loop (pre-implementation design)

Product review at the report-design stage raised the harder question before any Mission code:
**the report is a transition point, not an end point.** A plan that is generated once, exported,
and never touched again is a document; the product's differentiator is a plan that stays a *live*
object — tasks get done, evidence gets attached, and the organization's maturity genuinely moves,
visibly, over weeks. This section designs that loop: `Discovery → Analysis → Report → Approve →
Create Tasks → Execution → Evidence → Completion → Recalculate Maturity`. Two decisions carry the
whole design: **the Mission stays bounded** (it produces the plan and then completes — Missions
are not a shape that fits "runs for months"), and **maturity recalculation is not new inference**
— it is the *same* deterministic `_score_maturity` pass Tier B already runs, re-run later against
updated facts. No new AI decision-making is introduced anywhere in this section.

#### 5.1 Where the Mission ends and the living Plan begins

`generate_governance_plan` (§3) is unchanged: `resolve_applicability → gather_control_library →
synthesize_plan`, approval-gated, terminating `COMPLETED`. What §3 left implicit and this section
makes explicit: **on approval, before completing**, the Mission's resume path computes each item's
`due_at` from its `timeframe_bucket` and the plan's creation time (a fixed, deterministic offset
table — `week_1→+7d, week_2→+14d, month_1→+30d, month_3→+90d, month_6→+180d, year_1→+365d`) and
sets every item's initial `status='not_started'`. This is "Create Tasks" — it is the tail of the
*same* bounded Mission, not a new one: the Mission's job was always "produce a plan," and a plan
without dates and initial state isn't finished being produced.

Everything after that — **Execution, Evidence, Completion, Recalculate Maturity** — is NOT
Mission-governed. It is ordinary domain behavior on the `GovernancePlan`/`PlanItem` aggregate,
exposed through a new, small **Plan Execution service** (mirrors `governance-session`'s role
relative to Discovery — a domain service outside the Mission Engine, not a new Port; CLAUDE.md §16
is explicit that a direct call beats an event bus for simple in-transaction reads/writes, and
marking one task done is exactly that). This is the same category of decision as §2's "the
interview doesn't fit Mission shape," applied a second time: ongoing task tracking across weeks is
even further from "bounded, governed work" than a conversational interview was.

#### 5.2 Every recommendation explains itself — no new fields, real content

The requirement ("Why? / What will it achieve? / What happens if ignored?") maps onto columns
`governance_plan_items` has carried since Phase 0 and never used for real content:
`rationale` = **Why** (must name the specific gap/signal that triggered it, e.g. "no risk register
was found, and the organization runs multiple operational processes — risks are unlikely to be
caught early"), `expected_outcome` = **What it achieves**, `risk_if_skipped` = **the impact of
ignoring it**. Phase 3's per-item LLM drafting role (§3 step 3) must populate genuinely tailored
text for all three, grounded in that item's own `source_signal_keys`/`source_framework_refs` —
never generic boilerplate ("consider improving governance"). This was already the design intent;
this review just makes "all three fields, every item, specifically grounded" a hard requirement
rather than an implicit one.

#### 5.3 Completion → recalculated maturity — reversible by construction, not by undo logic

Every `plan_seed` that remediates a specific gap may declare what completing it is *equivalent to*
in the same Signal vocabulary the interview already speaks:
```
"plan_seed": { "id": "seed:establish_risk_register", ...,
  "resolves_signal": { "signal": "risk_register_state", "value": "approved" } }
```
`resolves_signal` is optional (some items — e.g. "adopt a technical security baseline" — are too
broad to collapse into one signal, and completing them just updates status with no signal
effect). When present, it is copied onto the persisted `governance_plan_items.resolves_signal`
column **at plan-creation time**, not looked up from the live pack file later — the same
reproducibility reason `discovery_sessions.pack_versions` is pinned (a pack update six months from
now must never silently change what completing an old item does).

**Revised design (product review: completion must be undoable — re-checking "Completed" must
cleanly revert, not require separate undo logic):** `organization_profiles.signals` is a frozen
**baseline** — populated exactly once, when a discovery session concludes (this is the fix for the
bug §5.6 surfaces), and never mutated by task completion. The organization's **current** signal
state is never stored — it is **computed fresh, every time**, as a pure function:

```
effective_signals(tenant) = baseline_signals(tenant)
                             ⊕ { resolves_signal for every governance_plan_item
                                 currently status='done', ordered by completed_at }
```

(`⊕` = later entries overwrite earlier ones for the same signal key — the rare case of two
different completed items resolving the same signal.) This is a new pure function in
`governance-discovery` (no I/O — it takes a baseline `SignalSet` and a list of `(signal, value,
completed_at)` triples and returns a `SignalSet`, fully unit-testable without a database), and
"current maturity" is simply `_score_maturity(effective_signals(tenant), active_packs)` — the
*exact same* function §1's Tier B already runs, called again later on different input. Still zero
new inference.

The payoff of computing rather than mutating: **reverting is not a separate code path.** Un-marking
an item as `done` requires nothing but changing its `status` back — the next time anyone asks for
current maturity, that item's `resolves_signal` is simply no longer in the "currently done" set,
and `effective_signals` recomputes correctly with no trace of it, automatically. There is no stored
mutation to undo because nothing was ever mutated. `governance_plans.maturity_baseline` stays
frozen (the report's original snapshot) throughout, so a dashboard can always show "you started at
⭐⭐☆☆☆, you're at ⭐⭐⭐⭐☆ now, heading toward the ⭐⭐⭐⭐⭐ Governance Vision" — three points on
the *same* deterministic scale. Marking a task done is itself the practitioner's attestation — no
separate AI approval gate applies (CLAUDE.md's "human proposes, human decides" is satisfied by the
human directly deciding their own org's state, not an AI proposing a change for them to ratify).

Every status transition (`done`/`reopened`) is still appended to a new, append-only
`governance_plan_events` table (mirrors `discovery_answers`' audit-log discipline exactly: `id,
plan_item_id, tenant_id, event_type ('completed'|'reopened'|'evidence_attached'), actor_id,
created_at`) — the audit trail CLAUDE.md §19 requires, and the natural future seam for
reminders/notifications (§5.5) once a second consumer of "something happened" exists — deliberately
not wired to the full `event-bus`/`OutboxSink` machinery Missions use, per the Port-Worthiness
principle: one table, one consumer today; upgrade the seam only when a second real consumer shows
up, not preemptively. Unlike the earlier draft, this log is now purely a **record of what
happened**, not a mechanism anything else depends on to compute current state — current state is
always derived fresh from §5.3's formula, so the log can never drift out of sync with it.

#### 5.4 Evidence — always optional, never a gate

Product review: evidence must never block completion — a small organization with no formal
evidence trail must be able to mark a task done on their word alone, while a more mature
organization that *does* attach evidence gets that reflected. `governance_plan_items` gains
`evidence_ids jsonb NOT NULL DEFAULT '[]'`, following the *exact* naming convention `apps/web`
already uses for the reverse direction (`evidence.control_ids` links an Evidence record to
framework controls — `lib/evidence/types.ts`, migration `0003_evidence.sql`). Completion never
checks whether this array is non-empty — structurally optional, not a soft UI nudge that becomes a
hard requirement later. What it *does* change: an item with `evidence_ids` non-empty at completion
time is labeled **"Evidence-backed"**; empty is labeled **"Reported by [user]"** — same wording
distinction, same underlying provenance concept as the interview's own `evidence_backed` Signal
type (§2.3), just surfaced as a UI badge here instead of a `confidence` field. A natural, later
enhancement (not built now): surface existing Evidence whose `control_ids` overlap an item's
`source_framework_refs` as a suggestion — the two id spaces already point at the same framework
catalog.

#### 5.5 Reminders (mechanic named, deferred to Phase 5+)

Deadlines/reminders need a time-based scan, not a request-response call — the right shape is a
**Scheduled Job** (one of the Tool Registry's six official callers, CLAUDE.md §9), not a new
service: `scan_overdue_plan_items`, run on a schedule, querying `due_at` against `now()` and
writing to `governance_plan_events` (`event_type='reminder_due'`), which the product's existing
notification surface (`NotificationsMenu`) consumes. Deferred because it needs no new mechanic
beyond what §5.3 already introduces (the events table) — only the scheduled Tool and the
notification wiring, both Phase 5+-sized, not architecture.

#### 5.6 Confidence per recommendation

Product review: each recommendation should show a Confidence percentage — not the AI "hedging,"
but a direct reflection of how much of it rests on clearly-stated facts versus thin or incomplete
information. Computed with **no new inference**, from two numbers the engine already produces:

1. **Signal support**: every rule's predicate already names which signal keys it reads. A new pure
   function in `predicate.py`, `referenced_signals(expr) -> frozenset[str]` (a small generalization
   of the existing `references_signal`, same tree-walk), collects all of them for the rule that
   fired a given `plan_seed`. That rule's signal-support score is the mean of `Signal.confidence`
   across those keys — 1.0 today for every direct-entry answer (§2.3), but this is exactly the
   number that drops for a free-text answer resolved by the (already-designed, not-yet-built)
   bounded LLM normalizer, or rises to a full 1.0 only when `evidence_backed`.
2. **Interview completeness**: the session's own `confidence_score` (§2.4 — answered-required /
   total-required-for-this-org), already computed once per session.

`item_confidence = round(signal_support × session.confidence_score, 3)`, computed in `analyze()`
alongside each `plan_seed` and carried through the Scheduler into `governance_plan_items.confidence`
(§5.7's new column) — shown as a percentage next to every recommendation. This is honest about what
it currently expresses: with today's Knowledge Packs (only direct-entry answers), most items will
read close to 100%, and a session with several skipped optional/required questions systematically
lowers *every* item's shown confidence, not just the ones that skip touched — which is correct: an
incomplete picture of the organization makes every conclusion about it less certain, not only the
directly-affected ones. Real per-item spread (one recommendation at 98%, another at 72%, from the
*same* session) appears once free-text answers or partial coverage enter a specific rule's signal
set — the mechanism is ready for that the moment §2.3's LLM normalizer role is built; it is not
faked in the meantime.

#### 5.7 Data model additions (all additive to schema/tables that already exist, none shipped yet)

- `governance_plans`: + `version integer NOT NULL DEFAULT 1`, + `previous_plan_id text` (nullable
  self-reference), + `maturity_at_supersession jsonb` (nullable — set only when superseded) (§3.1).
- `governance_plan_items`: + `resolves_signal jsonb` (nullable), + `evidence_ids jsonb DEFAULT
  '[]'`, + `confidence double precision` (§5.6).
- New table `governance_plan_events` (append-only, `governance-store` package, same migration
  discipline as every other table in ADR 0066): the audit log for §5.3/§5.5 — `id, plan_item_id,
  tenant_id, event_type ('completed'|'reopened'|'evidence_attached'), actor_id, created_at`.
- No change to `organization_profiles`'s columns — `signals`/`active_packs` were already exactly
  what §5.3's baseline needs; they were simply unpopulated until this design gives them a first
  real writer: session conclusion (the bug this ADR surfaced — nothing today copies
  `discovery_sessions.signals`/`active_pack_ids` into `organization_profiles` when a session
  concludes; Phase 3 implementation must add that one write, and it is a prerequisite for §5.3's
  `effective_signals()` to have a baseline to compute from at all).

## Consequences

**Positive**
- Zero changes to the frozen Mission lifecycle, Tool contract, agent roster, or Framework Engine
  model — this is purely additive, same shape as ADR 0047/0050/0051.
- Composable Knowledge Packs model real organizations (multi-industry, multi-capability) instead
  of forcing a single label — and avoid a full redesign later when the catalog grows to packs like
  Remote Workforce, Cloud Provider, or AI Provider that cut across "industries."
- Typed signals (especially ordered `enum` maturity scales and real `numeric` counts) make
  maturity scoring and capacity scoring proportional rather than coarse, and keep the door open
  for `evidence_backed` corroboration against the platform's existing Evidence/RAG layer.
- The generated plan's pacing reflects the organization's actual ability to execute, not a
  one-size-fits-all template — a direct, auditable function of capacity signals.
- The interview engine remains pure, deterministic domain logic, independently unit-testable with
  golden scenarios, with no Mission/LLM machinery required to test pack activation, question
  routing, inference, or scheduling.
- Every inferred framework, maturity/capacity score, and plan item is traceable to the exact
  signals, packs, and framework controls that justified it, satisfying CLAUDE.md §19
  auditability.

**Negative / costs**
- Two new bounded contexts and one new package to maintain (`governance-store`), plus a future
  `governance-discovery` engine package (tracked for Phase 1).
- A shared signal-key vocabulary and typed value model is a coordination cost: every new Knowledge
  Pack must be reviewed against it rather than freely inventing keys or types — an intentional
  constraint, not a defect.
- The scheduler adds a genuine algorithmic component (deterministic bin-packing with dependency
  ordering) beyond simple rule evaluation — more surface to test, though it stays outside the LLM
  boundary and is fully unit-testable without one.
- The Mission (`generate_governance_plan`) can only start after a session concludes; the interview
  itself has no Mission-level durability/retry semantics (it relies on `discovery_sessions`
  persistence directly, not the Mission Engine's recovery machinery). Acceptable because the
  interview is idempotent to resume from the last answered question by construction (Tier A
  recomputes pack activation and question eligibility from stored signals).

## Alternatives considered

- **A single `industry_id` per session.** Rejected after product review: real organizations are
  multi-industry/multi-capability, and a single label loses most of the applicable knowledge (a
  technology company that is also a FinTech, cloud provider, and AI provider). Composable Knowledge
  Packs with independent activation predicates were adopted instead.
- **A flat yes/no answer set for all process/policy questions.** Rejected: governance maturity is
  not binary. Replaced with an ordered 5-level maturity `enum` as the default scale, plus real
  `numeric`/`date`/`percentage` types where the underlying fact is not categorical at all (e.g.
  employee count as an exact number, not a size band).
- **Fixed timeframe buckets baked into each rule (Week 1 = N tasks, always).** Rejected: it ignores
  execution capacity and can hand a 3-person firm an unexecutable week and under-schedule a large
  enterprise. Replaced with capacity-agnostic `plan_seed`s (urgency + effort + dependencies) and a
  deterministic, capacity-aware Scheduler that computes the actual bucket assignment.
- **Model the interview as Mission steps (one step per question).** Rejected: the frozen
  `MissionStatus` enum has no conversational-pause state, and turning UI turn-taking into
  Mission/Tool steps is a category error — Missions govern auditable *work*, not interactive
  question-answering. Would also have required amending the frozen Core.
- **Incremental, per-answer framework/maturity inference.** Rejected: the owner requires that no
  plan/result data ever be visible during the interview; a single one-shot analysis at conclusion
  is both simpler and a cleaner enforcement of that requirement.
- **LLM-driven free-form interview control flow, or an LLM deciding plan timing/scheduling.**
  Rejected: violates CLAUDE.md §6 pillar 8 (never trust raw LLM text as control flow without
  validation) and undermines reproducibility (§19) — both question routing/inference and schedule
  computation stay deterministic and replayable; the LLM only drafts prose after every structural
  and timing decision is already fixed.
- **A graph database / generic knowledge-graph engine for applicability.** Rejected: "gap
  correlation" reduces to multi-signal predicates, not graph traversal; a declarative rule table
  meets every stated requirement without introducing a new architectural Port that has no second
  realization in view.
- **A framework-picker screen.** Explicitly rejected by product requirement — the user must never
  select a standard by name.

## Appendix A: initial signal-key vocabulary (extended by data, not code)

Core, pack-independent signals (typed):
- `boolean`: `has_branches`, `handles_personal_data`, `has_gov_clients`, `has_board`,
  `has_legal_team`, `has_it_team`, `has_compliance_officer`, `has_committees`, `has_licenses`.
- `enum` (default maturity scale `absent < verbal < documented_unapproved < approved <
  reviewed_periodically` unless noted): `org_structure_state`, `policy_state`,
  `risk_register_state`, `internal_audit_state`.
- `enum` (custom scale): `execution_capacity`
  (`none < ad_hoc < allocated_time < dedicated_budget < dedicated_team_and_budget`),
  `offers_services_vs_products` (`services | products | both`).
- `numeric`: `employee_count`, `branch_count`.
- `percentage`: `remote_workforce_share`.

Pack-activation signals (examples; each pack's own file is authoritative):
`primary_activity` (drives the initial dropdown → activates one or more packs), `provides_saas`,
`provides_cloud_infrastructure`, `provides_ai_services`, `has_online_store`,
`employs_remote_staff`.

New keys are proposed by adding to this appendix via PR, not invented inline in a Knowledge Pack.

## Revision history

- 2026-08-02 (initial): single `industry_id` per session, flat yes/no-centric answer set, fixed
  timeframe buckets per rule.
- 2026-08-02 (revised, same day, pre-implementation): composable Knowledge Packs replacing
  `industry_id`; typed Signals (`boolean/enum/numeric/date/percentage/evidence_backed`) replacing
  the flat answer set; execution-capacity-aware deterministic Scheduler replacing fixed timeframe
  buckets. No code had shipped against the initial revision — schema and package scaffolding from
  Phase 0 are updated in place rather than superseded.
- 2026-08-02 (Phase 2 addendum): added "Frontend integration" — `apps/web` wired to `v2/apps/grc-api`
  (ADR 0052's host) via thin Next.js proxy routes, and an interim HMAC-signed service-assertion
  identity bridge, both live-verified end-to-end through a real Postgres-backed session. Also added
  `ui_hint`/`allow_multiple`/`required` to `Question` and `ValueType.TEXT` (free-text, non-structural)
  — extensions to §2.3/§2.2 the interview UI needed, not a change to any decision already made.
- 2026-08-02 (Phase 3 report-design addendum, §4): finalized the ten-section consulting-style
  report structure. Implemented now, ahead of the Mission itself: `MATURITY_DIMENSIONS` renamed/
  regrouped to `governance/risk/compliance/cyber/leadership` (new `leadership` dimension, new
  `has_board` question), `stars_and_label()` pairing a 0–5 star count with a label,
  `Applicability.maturity_vision` (a second deterministic pass over a "best case" SignalSet), and
  `BUCKET_ORDER` widened from 5 to 6 periods (`week_1/week_2/month_1/month_3/month_6/year_1`).
  Frameworks are default-hidden from the client-facing report (progressive disclosure, not
  concealment — CLAUDE.md §19 satisfied by availability, not prominence). All of the above is
  implemented and tested in `governance-discovery`/`governance-store`/`grc-api`/`apps/web`; only
  the two new bounded LLM narrative roles and the Mission's `PLAN_SYNTHESIS_TOOL` remain (Phase 3
  proper).
- 2026-08-02 (§5, pre-implementation): design-only — before writing the Mission, designed the full
  post-approval lifecycle (Create Tasks → Execution → Evidence → Completion → Recalculate
  Maturity) explicitly, per product direction that the plan must be a living object, not an
  exported document. Key resolutions: the Mission stays bounded (ends at "Create Tasks," the tail
  of `synthesize_plan`'s resume path); everything after is a new, non-Mission **Plan Execution**
  domain service (same category of decision as Discovery living outside the Mission Engine);
  maturity recalculation is the *same* `_score_maturity` function re-run against updated
  `organization_profiles.signals`, not new inference; a new optional `resolves_signal` on
  `plan_seed` (pinned onto the persisted item at creation time) is what lets a completed task write
  back to the Signal store. Surfaced one real gap for Phase 3 to fix: nothing today copies a
  concluded `discovery_sessions.signals` into `organization_profiles`. No code written yet — this
  entry is the design of record pending owner confirmation before implementation.
- 2026-08-02 (§5, revised before implementation): four corrections from product review. (1)
  Reversibility: replaced "write `resolves_signal` into `organization_profiles.signals`" with
  computing current state fresh every time (`effective_signals` = frozen baseline ⊕ every
  currently-`done` item's `resolves_signal`) — un-completing a task now needs no undo logic, it
  falls out of the formula for free. (2) Evidence is structurally optional everywhere, never a
  completion gate — only changes the "Evidence-backed" vs "Reported by [user]" label. (3) New §5.6:
  per-recommendation Confidence, computed from existing `Signal.confidence` (via a new
  `predicate.referenced_signals`) and the existing session `confidence_score` — still zero new
  inference. (4) Confirmed, no change needed: Plan Execution is not a Mission (execution can run a
  year; a Mission cannot), and the `discovery_sessions.signals → organization_profiles` gap is
  confirmed as a Phase 3 fix.
- 2026-08-03 (§3.1, design approved, implementation begins): added "Governance Plans are immutable
  snapshots" — a new plan is always a new `governance_plans` row (`version`, `previous_plan_id`);
  the prior active plan transitions to `superseded` with a `maturity_at_supersession` snapshot,
  never edited or deleted. `governance_plan_items`/`governance_plan_events` stay permanently
  attached to the version that created them. Design phase for ADR 0066 closes here — Phase 3
  implementation (the Mission, the two LLM roles, Plan Execution, and this versioning scheme)
  begins next.
- 2026-08-03 (§3, implementation-driven correction): split `synthesize_plan` into `draft_plan`
  (produces the reviewable content) + `finalize_plan` (consequential, persists after approval).
  Discovered while implementing: the Mission Engine's approval gate pauses BEFORE a consequential
  step runs, not after — a single combined step would have made the human approve blind. §5.1–§5.7
  (Plan Execution, reversible maturity, confidence, evidence, immutable snapshots) are all now
  implemented and tested in `governance-discovery`/`governance-store`/`governance-plan-execution`
  ahead of this Mission; this entry only concerns the Mission/tool shape itself.
- 2026-08-03 (Phase 3 complete): the Mission, the two LLM roles, Plan Execution, and the versioning
  scheme are implemented, tested, and wired into `grc-api`. Corrections found during this last leg:
  (1) `generate_governance_plan`'s input is `inputs["request"]`, not `inputs["discovery_session_id"]`
  as §3 originally said — every builtin Capability reads its one opaque input string from the same
  `"request"` key (`grc_api/adapters.py`'s `CatalogDefinitionProvider.define` hardcodes `{"request":
  scope}`; there is no per-capability input key today), so the REST caller passes the concluded
  session id via `CreateMissionBody.scope`, same as Gap Assessment passes a control domain. (2)
  Creating/running the Mission needed no new endpoint — `generate_governance_plan` is just another
  Mission Catalog entry, so it goes through the existing generic `POST /v1/missions` → `.../run` →
  ADR 0044 approval flow unchanged. What *is* new is `/v1/governance-plans/*` (`grc_api/routers/
  governance_plans.py`): `GET .../active`, `GET .../versions`, `GET .../{plan_id}`, `GET .../maturity`
  (§5.3's live, reversible recalculation), and the execution actions `POST .../items/{id}/complete`,
  `.../reopen`, `.../evidence` — all thin adapters over `PlanExecutionService`/`PostgresGovernanceStore`,
  no Mission involved (§5.1). (3) Deliberately left untouched: `grc-api`'s production default
  executor is still `EchoExecutor` — replacing it with a real `ToolRegistry`-backed one is the
  separate, already-tracked Wave 1 migration commit (`tests/production/test_production_defaults.py`),
  and flipping it here would have required standing up a production `GenerationProvider` (no such
  wiring exists anywhere in the repo yet) and a full `local_search`/`run_pipeline` tool set for
  every other mission type — well beyond this ADR's scope. Instead, a new DB-gated end-to-end test
  (`grc-api/tests/production/test_governance_plan_e2e.py`) injects a real registry-backed executor
  via the same `executor=` seam every other test in that suite already uses, with a deterministic
  fake `GenerationProvider` (CLAUDE.md: never a live LLM call in a unit test) — proving the full
  chain (create → run → pause at the gate → approve → immutable snapshot persisted → read via the
  new routes → complete an item → maturity recalculates → reopen → maturity reverts → a second plan
  supersedes the first → tenant isolation holds) works through the real API today, and will run for
  real the moment the Wave 1 executor commit lands, with zero additional code.
- 2026-08-03 (Phase 3 Production Hardening): a PR-style review before closing Phase 3 surfaced five
  data-integrity gaps the happy-path implementation and tests hadn't exercised — none architectural,
  all confined to `governance-store`'s write surface. Fixed:
  1. **Item + event atomicity**: `record_item_transition()` replaces separately-called
     `save_plan_item()`/`append_plan_event()` — both writes now happen inside one
     `with self._conn.transaction():` block (the autocommit connection's per-statement-commit
     behaviour meant a crash between them could previously leave a "completed with no event" item).
  2. **Optimistic locking**: `record_item_transition()`'s UPDATE is gated
     `WHERE updated_at = expected_updated_at` (the version `PlanExecutionService` last read). A
     losing concurrent writer gets `False` → `PlanItemConflict` → HTTP 409, never a silent lost
     update (e.g. one user's `attach_evidence` overwriting another's).
  3. Immutable snapshots (§3.1) confirmed correct as designed — no change needed.
  4. **Defensive tenant check**: `append_plan_event()` now verifies `plan_item_id` actually belongs
     to the given `tenant_id` (a `SELECT` before the `INSERT`) rather than trusting the caller;
     `record_item_transition()` gets this for free from its own UPDATE's `WHERE` clause.
  5. **DB-layer immutability, not just convention**: `save_plan()`/`save_plan_item()` (general
     upserts) are gone, replaced by `create_plan()`/`create_plan_item()` (INSERT-only) and
     `supersede_plan()` (the one legitimate status transition, `WHERE status = 'active'` — a second
     attempt is a harmless no-op, not a re-edit). There is no longer a write path capable of
     rewriting a plan's or item's content after creation — not by convention, by construction.
  6. **Deterministic event ordering + a read path**: `governance_plan_events` gained
     `sequence bigint GENERATED ALWAYS AS IDENTITY` (a race-free, database-assigned tie-breaker —
     `created_at` alone cannot order two events sharing a timestamp) and a new `list_plan_events()`
     / `GET /v1/governance-plans/items/{id}/events` — the audit trail was write-only before this.
  `PlanFinalizeTool`/`PlanExecutionService` updated to the new store surface; 247 tests green across
  every touched package (governance-discovery/store/session/plan-execution/plan-tools, grc-api,
  assistant-runtime), including new tests for the lock, the tenant check, the supersede-once
  guarantee, and sequence ordering under identical timestamps.
- 2026-08-03 (transaction atomicity, verified not just read): the hardening entry above claims
  `record_item_transition()`'s item-UPDATE and event-INSERT commit or roll back together. Verified
  directly against a real database rather than by code inspection: a live run that makes the item
  UPDATE succeed (`rowcount > 0`) and THEN forces the event INSERT to fail (a colliding primary
  key) shows the item's `status`/`updated_at` revert to their pre-call values — `psycopg3`'s
  `with self._conn.transaction():` rolls back the whole block on the exception, including the
  already-executed UPDATE, even though the underlying connection is `autocommit=True`. This is now
  a permanent regression test
  (`test_record_item_transition_rolls_back_the_item_update_if_the_event_insert_fails`), alongside
  the existing one proving the optimistic-lock-rejection path writes no event either. 24/24 in
  `governance-store`.
- 2026-08-03 (**Phase 3 closed** — design and data-integrity, within its declared scope): the
  Mission, the two LLM roles, Plan Execution, the immutable-snapshot versioning scheme, and the
  Production Hardening pass above are complete, tested (247 tests), and verified — both by
  inspection and by forcing real failure conditions against a live database, not inferred from
  reading the code. **Explicitly out of this closure's scope**, tracked separately and
  deliberately not folded in here: (a) the Wave 1 migration replacing `grc-api`'s production
  default `EchoExecutor` with a real `ToolRegistry`-backed one (`tests/production/
  test_production_defaults.py`) — the Mission runs for real today via the `executor=` injection
  seam this ADR's own tests use, and will run for real by default the moment that separate,
  already-tracked commit lands, with zero further change here; (b) Phase 4 (Plan view + dashboard
  rework — no frontend UI consumes `/v1/governance-plans/*` yet); (c) Phase 5 (seed sector data
  beyond `core`/`technology`/`cloud_provider`). Reopen with a new revision entry, not a silent
  edit, if a later phase's work surfaces a genuine defect in what is closed here.
- 2026-08-03 (**Phase 4 — Product Flow Simplification, closed**): a UX audit ("does the user know
  where they start and end?") found that (b) above was more than a missing page: **no code
  anywhere in `apps/web` had ever created or run the `generate_governance_plan` Mission** —
  `/plan`'s empty state was the only thing a real user could ever reach, and the interview's
  conclusion screen was a Phase-2 stopgap (`DiscoveryResultPreview`) showing 4 of the report's ten
  designed sections. Fixed by wiring the actual bridge and collapsing Discovery/Report/Plan into
  one journey rather than three pages:
  - New `apps/web/lib/planGeneration/` proxies the generic `/v1/missions` contract exactly as
    `lib/discovery/service.ts` already proxies `/v1/discovery/*`: `startPlanGeneration` creates and
    runs the Mission in one call (the three non-consequential steps run synchronously; the Mission
    pauses at `finalize_plan`, the one consequential step), `getPendingPlanGeneration` resumes a
    session left `awaiting_approval`, `approvePlanGeneration` crosses the ADR 0044 gate. The
    `draft_plan` step's output is read via `findings[i].summary` (`MissionDetailView`), guarded by
    matching the step's own `description` before trusting its index, so a future change to this
    Mission's shape fails loudly instead of silently parsing the wrong step.
  - `POST /v1/missions/{id}/approvals/{step_id}/approve` requires the grc-api role literal
    `"approver"`, which `apps/web` has no such role for — `owner`/`admin`/`compliance_manager` are
    mapped to grant it only when minting the service-assertion token (`serviceToken.ts`'s `roles`
    param), enforced both client-side (button disabled) and server-side (403 in the Next.js route)
    ahead of grc-api's own independent check — three layers, not decorative redundancy.
  - `components/discovery/DiscoveryFlow.tsx`'s phase machine gained `report` (replacing `result`)
    and `activating`; `components/governance/GovernanceReport.tsx` (+ `JourneyStepper.tsx` and five
    section sub-components) renders the full ten-section report from §4 for the first time, ending
    in the "Approve & Activate Plan" action — the ADR 0044 gate, visible in the product for the
    first time. `DiscoveryResultPreview.tsx` and its dead `GET .../result` route are deleted.
  - `app/[locale]/(app)/discovery/page.tsx` is now the single entry point: it redirects
    server-side to `/plan` when `getActivePlan` finds one, so "I already finished this" always
    lands the user in the right place; `?restart=1` is the one deliberate escape hatch, linked from
    `/plan`'s low-emphasis "Run a new assessment." The sidebar's separate `plan` nav entry is
    removed — one nav item ("Governance Program") for the whole journey.
  - **A real deployment gap, not a frontend bug, blocked end-to-end verification and is now
    fixed**: `mission_read_model` (the table `GET /v1/missions` reads —
    `mission-read-model/mission_read_model/schema.py`) had DDL but, unlike `mission-store`'s
    `missions`/`outbox` tables, no committed `.sql` migration — the package's own docstring named
    this a "(later)" migration that was never actually written. Any real (non-test) deployment's
    `GET /v1/missions` 500s from the first `SELECT` on a fresh database; nothing in the production
    test suite caught it because `tests/production/conftest.py` creates the table itself, in
    Python, at test setup, masking the absent migration. Fixed with
    `mission-read-model/migrations/0001_mission_read_model.sql` (identical DDL to `schema.py`'s
    `create_table_sql()`, the same idempotent `CREATE TABLE IF NOT EXISTS` style as every other
    migration in this ADR). Verified end-to-end against a real Postgres database with this
    migration applied, and separately against a real `RegistryExecutor` + deterministic fake
    `GenerationProvider` (the same injection this ADR's own `test_governance_plan_e2e.py` uses)
    standing in for the still-`EchoExecutor` production default — confirming the whole chain
    (interview → real Mission → ten-section Report → approve → `/plan` → re-visiting `/discovery`
    redirects straight back → Arabic/RTL) works, in both directions (fresh session and
    resume-mid-report), for an approver and a non-approver role alike.
  - Explicitly unchanged: the Wave 1 `EchoExecutor` → `RegistryExecutor` production-default
    migration remains separate, already-tracked work, per (a) above — this closure only fixes the
    unrelated `mission_read_model` migration gap that any Mission type's list endpoint would hit
    regardless of which executor is wired.
