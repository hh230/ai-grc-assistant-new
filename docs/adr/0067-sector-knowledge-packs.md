# ADR 0067: Sector Knowledge Packs — LLM-authored knowledge, human-approved, version-pinned

- Status: **Accepted** — 2026-08-07, *with changes*. The owner required four amendments before
  implementation, all applied here: an `Assessment` entity between organization and selection; an
  explicit **Active Release Pointer** replacing "newest un-superseded row"; reproduction metadata
  (model, prompt version, generator commit) on every release; and the **Knowledge Freeze** rule.
- Date: 2026-08-07 (amended the same day)
- Deciders: Product owner; platform engineering
- Related: CLAUDE.md §1 (trust is the product), §6 (grounding over generation; determinism at the
  edges), §9 (human approval gates), §13 (frameworks are data), §15 (ubiquitous language), §19
  (transparency & reproducibility), §23 (ADRs); ADR 0044 (Human Approval Lifecycle), 0045 (V2
  persistence style), 0050 (Framework Library — frameworks as data), 0066 (Governance Discovery
  & Planning)

## Context

ADR 0066 built a two-tier adaptive interview over hand-authored Knowledge Packs, feeding a
deterministic rule engine that computes maturity, gaps, capacity-aware scheduling, dependencies
and per-recommendation confidence. That engine works and is the product's defensible core.

Its knowledge does not scale by sector. Measured on the shipped packs: **thirteen industries
produce three distinct plans**, because writing a rule set per sector by hand is a combinatorial
cost nobody pays — so in practice nobody wrote any, and `primary_activity` became close to
decorative. A Saudi real estate brokerage is never asked about its FAL licence; a clinic is never
asked about patient data handling. This is the single highest-impact gap in the product backlog.

At the same time, both `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are now configured, and provider
selection was global — one `GRC_LLM_PROVIDER` for every purpose — so which model wrote a
customer's compliance advice was a deployment detail.

Four forces bound any solution:

1. **Trust is the product.** An LLM that authors compliance questions authors them for *every*
   organization in that sector at once. A wrong question is not one bad plan; it is a systematic
   defect distributed to every customer who follows.
2. **Reproducibility.** A report issued today must be reconstructable in three years (CLAUDE.md
   §19). Knowledge that changes underneath a customer breaks that.
3. **The engine must stay the decision-maker.** Maturity, gaps, priorities and risk are computed
   and auditable today. Moving them into a prompt would trade an explicable system for a
   convincing one.
4. **Cost and latency.** Calling an LLM per customer to produce the interview is both expensive
   and non-deterministic across customers in the same sector.

## Decision

We will add a **Sector Knowledge Pack** layer: Claude authors the sector half of the interview
**once per sector**, the output is reviewed and released as a versioned knowledge asset, and every
customer in that sector is interviewed from the released asset with no further LLM call.

Eight binding decisions.

### 1. LLM providers are selected by ROLE, and the split is enforced

Two roles:

| role | purpose | provider |
|---|---|---|
| `GOVERNANCE` | sector knowledge generation; governance plan drafting | **Claude only** |
| `TECHNICAL` | documents, OCR, classification, embeddings, retrieval | OpenAI by default |

`resolve(GOVERNANCE, …)` **raises** if configured with a technical-tier provider, and the general
`GRC_LLM_PROVIDER` deliberately does not feed the governance role at all. Changing which vendor
writes compliance advice is a code change in review, never a deployment variable.

Each role takes its model from that vendor's own variable (`ANTHROPIC_MODEL` / `OPENAI_MODEL`).
This is not cosmetic: the Claude adapter's built-in default is an Opus model, so a configured
Sonnet must be passed explicitly or the wrong model runs silently, at several times the cost.

### 2. Claude is responsible for LANGUAGE, not for TRUTH

A generated question may carry editorial metadata: `category`, `importance`, `references[]`,
`why_we_ask`, `evidence_required`. It may **not** carry anything the decision engine acts on. Ten
fields are refused outright rather than ignored — `writes_signal`, `signal`, `rule`, `rules`,
`predicate`, `effect`, `severity`, `maturity_delta`, `priority`, `plan_seed`, `resolves_signal` —
because a field silently dropped today is a field someone relies on tomorrow, and a regulatory fact
living inside a prompt is a fact nobody can replay.

Consequently:

- **Sector answers are not Signals.** A Signal is a fact the engine relies on, and the knowledge
  register guarantees every signal drives a rule. "Do you hold a FAL licence?" is true of real
  estate and meaningless elsewhere; admitting it to the signal space would break that guarantee
  for every sector added afterwards. Sector answers travel their own path:
  `Discovery Answers → Core Signals → Sector Answers → Plan Context`.
- **The report is still assembled from engine output.** Claude receives the engine's maturity,
  gaps and recommendations *already decided*, plus the sector answers, and writes prose. This is
  the discipline the existing drafting prompts already enforce.
- Future sector-specific *rules* are welcome — as reviewable data in the rule engine, never as
  prompt text.

### 3. Arabic is the single source of truth; translations are a separate layer

Claude generates **Arabic only**. Every other language is a `QuestionTranslation` with its own
lifecycle (`Generated → Reviewed → Published`). Storing Arabic as a translation is refused.

Generating two languages in one call would make the product depend on two texts staying
semantically identical; the first reviewer to edit only the Arabic — or regenerate only the
English — forks the question silently, leaving two meanings and no record of which is
authoritative. Separation also means a third language is added without regenerating knowledge, and
`translation_coverage` answers "which languages are behind" with a number, counting **published
only**.

### 4. Six entities, each with one job

| entity | is | is not |
|---|---|---|
| `Industry` | a slug, an Arabic name, a status | a place for logic |
| `KnowledgeTemplate` | the container for one industry's knowledge | versioned content itself |
| `TemplateRelease` | one version's content + lifecycle + provenance | a status flag on the template |
| `ActiveTemplate` | one row per industry naming the release in force | derivable from timestamps |
| `Assessment` | one assessment of one organization, with a start and an end | a browser session |
| `TemplateSelection` | which release(s) an assessment was conducted under | an industry name |

**`Industry` carries no logic.** The pull towards `parent_industry`, `aliases`, `icon`,
`regulatory_family` is real and refused: each turns a lookup value into the axis of the system,
and the system's axis is the rule engine. What an industry *implies* belongs in derivations, where
it is auditable.

**The template is a container; the release is the version.** `KnowledgeTemplate` names an
industry's knowledge once; `TemplateRelease` carries each version's questions, its lifecycle and
its provenance. Build versus deploy.

A release moves `Draft → In Review → Approved → Released → Deprecated → Archived`. *In Review* is
the one state added beyond the owner's list, and it earns its place: without it, "still being
regenerated" and "waiting for a reviewer" are the same state, and the reviewer's queue cannot be
computed.

**Activation is an explicit pointer, never an inference.** `ActiveTemplate` holds one row per
industry naming the release in force. Two releases may be `Released` at once while only one is
active, which is what makes rollback cheap and honest:

    v4 released 10:00, ActiveTemplate -> v4
    a bad question is found at 11:00
    ActiveTemplate -> v3            (one pointer write; no release is modified, none is invented)

Deriving "active" from the newest row was rejected precisely because it forces a *new version* to
undo a bad one — polluting the version history with releases that exist only to reverse a mistake,
and destroying the record of what was actually live between 10:00 and 11:00.

**An assessment binds to a release, never to a sector name.** The chain is
`Organization → Assessment → TemplateSelection → TemplateRelease`. An `Assessment` is one
assessment process with a beginning and an end — not a browser session, which is interruptible and
may span several, and not the organization, which will be assessed repeatedly over years:

    Organization
      +- Assessment (2026) -> real_estate@v3
      +- Assessment (2027) -> real_estate@v5

Binding to the organization would erase the history of which knowledge produced which report;
binding to the session would tie a compliance record to a browser tab.

### 5. `primary_activity` suggests a template; a human decides

`suggest_template` proposes the newest released template for the answered activity and returns
**nothing** when none matches — a near-miss would show a reviewer sector questions written for
someone else and invite them to accept them.

The reviewer may choose a different industry, or several: reality is not one sector, and a
brokerage that also builds is "Construction + Real Estate". The suggestion is stored alongside the
decision, so a suggestion someone kept and a suggestion nobody examined stay distinguishable.

### 6. Every release carries what is needed to reproduce it

A release records `generated_by_model` (e.g. `claude-sonnet-5`), `prompt_version` (e.g.
`knowledge_prompt_v3`) and `generator_commit` (the SHA of the code that made the call).

In a year someone will open a question and ask why it exists. `why_we_ask` answers *why we ask
it*; these three answer *how it came to exist* — which model, which prompt, which code. Without
all three the generation cannot be repeated, and an output that cannot be repeated cannot be
audited (CLAUDE.md §19). A model version alone is not enough: the same model with a revised prompt
is a different generator, and so is the same prompt run by changed code.

### 7. Knowledge Freeze — a released asset is immutable, including how it was made

Once a release reaches `Released`, **nothing that produced it may change in place**: not the
questions, not the prompt version it was generated from, not the model. Any change produces a
**new release**.

This closes the gap the other rules leave open. Freezing the questions alone would still allow the
prompt or the model recorded against a release to be edited later, and the provenance in §6 would
then describe a generator that no longer exists — reproduction metadata that cannot reproduce.
Immutability has to cover the whole production path or it guarantees nothing.

Practically: prompt templates are stored versioned and append-only; a prompt edit mints a new
`prompt_version` rather than mutating one; and the store exposes no update path for a released
release's content.

### 8. Knowledge is never deleted, and never reaches a customer unreviewed

Two operational rules.

**No deletion after release.** Releases, questions and translations move to `Deprecated` or
`Archived`; a release replaced by a newer active one is `Superseded`. There is no `DELETE`, and no
hard delete in any repository method, because a report issued a year ago must remain literally
reconstructable.

**A separate approval role.** Approving a customer's plan and approving knowledge every customer
in a sector will be asked are different acts with different blast radii, so this does **not** reuse
the ADR 0044 `approver` role. A new `knowledge_approver` role gates the review workflow. Approval
without a recorded identity is refused: `approved_by` is the record of who accepted content that
will be put to every organization in the sector.

## Impact on the data model

New tables (V2 style per ADR 0045: hand-written idempotent DDL, `psycopg3`, parameterised SQL):

| table | holds | notes |
|---|---|---|
| `industries` | `slug` (PK), `canonical_name_ar`, `status` | no logic columns |
| `knowledge_templates` | `id`, `industry_slug` | the container; one per industry |
| `template_releases` | `id`, `template_id`, `version`, `status`, `expected_outputs`, `generated_by_model`, `prompt_version`, `generator_commit`, `created_by`, `approved_by`, `approved_at`, `released_at` | content + lifecycle + provenance; **immutable once `released`** |
| `release_questions` | `release_id`, `question_id`, `canonical_text_ar`, `type`, `options`, `required`, `category`, `importance`, `references` (jsonb), `why_we_ask`, `evidence_required` | `why_we_ask` never leaves the review console |
| `question_translations` | `release_id`, `question_id`, `language`, `text`, `status` | `language <> 'ar'` enforced |
| `active_templates` | `industry_slug` (PK), `release_id`, `activated_by`, `activated_at` | **one row per industry**; the PK is what makes two active releases impossible |
| `assessments` | `id`, `organization_id`, `started_at`, `completed_at` | one assessment, not a session |
| `template_selections` | `assessment_id`, `suggested_industry_slug`, `selected_release_ids[]`, `selected_by`, `selected_at` | what makes a report reproducible |
| `sector_answers` | `assessment_id`, `release_id`, `question_id`, `answer` | **not** signals |

`active_templates` having `industry_slug` as its primary key is deliberate: "two releases active
for one industry" becomes unrepresentable rather than merely discouraged. Rollback is one `UPDATE`
of `release_id`; every release row is untouched, and the activation history lives in an append-only
`active_template_history` companion so "what was live at 10:30?" stays answerable.

Existing tables are **unchanged**. `discovery_sessions`, `governance_plans`, `organization_profiles`
and the signal space keep their current shape.

## Impact on the API

New, all under `/v1/knowledge`:

| endpoint | role | purpose |
|---|---|---|
| `GET /industries` | any | selectable industries |
| `POST /industries` | `knowledge_approver` | register a new industry |
| `POST /templates/{industry}/generate` | `knowledge_approver` | one Claude call; creates a `generated` draft |
| `GET /templates/{industry}/{version}` | `knowledge_approver` | the review console view (includes `why_we_ask`) |
| `POST /templates/{industry}/{version}/submit` · `/approve` · `/reject` | `knowledge_approver` | the content lifecycle |
| `POST /releases/{id}/release` | `knowledge_approver` | mark a release `Released` (eligible to be activated) |
| `POST /industries/{industry}/activate` | `knowledge_approver` | point `ActiveTemplate` at a released release — this is also rollback |
| `GET /industries/{industry}/active` | service | the release an interview draws from |
| `GET /industries/{industry}/activation-history` | `knowledge_approver` | what was live, and when |

Changed: the discovery session response gains the sector questions of the selected release(s), and
the conclusion payload gains `assessment_id`, `template_selection` and `sector_answers`. All
**additive**.

## Backward compatibility

- **The existing interview is unaffected.** Layer 1 — the hand-authored `core`, `technology` and
  `cloud_provider` packs and every rule, derivation and signal — is untouched. An organization in a
  sector with no released template gets exactly today's interview and today's plan.
- **Existing plans stay valid and readable.** No column is dropped or repurposed.
- **The API is additive.** No existing route changes shape; new fields are optional and absent for
  sessions that predate a template selection.
- **Rollback of this ADR** is dropping the new tables and the `/v1/knowledge` routes. Nothing in
  Layer 1 depends on them.

## Migration strategy

Sequenced so each step is independently reversible and none blocks the product:

1. **Schema only.** Add the nine tables via `migrations/` and register them in `grc_api.migrate`.
   Nothing reads them. Deployable immediately; no behaviour change.
2. **Seed `industries`** from the thirteen existing `primary_activity` values, so the enum and the
   table agree from the start. The enum stays the interview's input; the table is the template key.
3. **Store + repository**, with `list`, `get`, `save`, and lifecycle transitions. Still unread by
   any interview.
4. **The generation tool and the review console.** Releases can now be generated, reviewed,
   approved, released and activated — but no interview consults `active_templates` yet, so
   activation still changes nothing a customer sees.
5. **Interview integration behind a flag.** An `Assessment` is opened per interview,
   `suggest_template` proposes the active release, the selection is recorded, and sector questions
   are appended after the core interview. Off by default; enabled per environment. This is the
   first step a customer can see, and the only one that needs a rollback plan of its own — turning
   the flag off restores today's behaviour exactly, because Layer 1 never changed.
6. **Plan context.** Sector answers reach the drafting step. The engine's output is unchanged; the
   report gains a sector section.

Steps 1–3 carry no customer-visible risk. Step 5 is the first that changes what a customer sees,
and it is the one behind the flag.

## Out of scope

This ADR does **not**:

- Move any decision into Claude. Maturity, gaps, priorities, risk and compliance stay in the rule
  engine, and sector-specific rules — when they come — will be reviewable data, not prompt text.
- Add sector-specific *rules*, derivations or signals. Only questions and their answers.
- Load NCA ECC, SAMA CSF or PDPL into the Framework Library. `references[]` are **labels for the
  reviewer**, never citations the product presents to a customer as authority; only the Framework
  Library may assert what a framework requires (ADR 0050).
- Ask customers for documents. `evidence_required` is captured now — retrofitting it would mean
  re-reviewing every published question in every sector — but nothing collects or verifies
  evidence.
- Translate anything automatically. The translation layer exists; filling it is separate work.
- Change the Mission approval gate, the plan lifecycle, or plan execution.
- Retrofit existing discovery sessions into `Assessment` rows. Sessions that predate this ADR keep
  working and simply have no selection; backfilling would invent provenance that never existed,
  which is the opposite of what these tables are for.
- Address the open launch blockers from the product readiness review: control-library linkage,
  expert review of the engine's recommendations, deployment, backup or monitoring.

## Consequences

**Positive**

- The highest-impact backlog gap closes: a new sector becomes a reviewed data asset, not a code
  change, and the second customer in a sector costs nothing.
- The engine stays the decision-maker, so the product's explainability and reproducibility
  survive the addition of an LLM to the knowledge path.
- Rollback of bad knowledge is a pointer move with full history, not a data edit.
- Which vendor writes compliance advice becomes a reviewed decision rather than a deployment
  variable.

**Negative / costs**

- A new human bottleneck: nothing reaches customers without a `knowledge_approver`. That is the
  intended trade — it is the control that makes LLM-authored knowledge acceptable at all.
- Knowledge Freeze makes fixing a typo in a released question cost a whole new release and review
  cycle. Accepted knowingly: a system where "it was only a small edit" is possible is a system
  where a report cannot be reconstructed, and the exception would be requested constantly.
- Seven new tables and a review console to build and maintain.
- Translation coverage becomes an ongoing operational obligation, visible and therefore chaseable.
- Sector knowledge is deliberately weaker than core knowledge: it informs the report but does not
  compute anything. Making it compute requires rules, in a later ADR.

## Alternatives considered

**A. Claude authors both the questions and the plan (replace the engine).** Rejected. It solves
the sector gap immediately and matches how most AI-first products work, but it discards maturity
scoring, gap detection, capacity-aware scheduling, dependencies and per-item confidence, and makes
the plan non-reproducible — the same answers could yield a different plan, in direct conflict with
CLAUDE.md §19. It trades an explicable system for a convincing one, in a domain where the product
*is* the explanation.

**B. Claude generates questions constrained to write existing Signals.** Rejected. It preserves
the engine, but forces every sector question into a cross-sector signal vocabulary that does not
fit it, and admits LLM-asserted facts into the space the knowledge register guarantees. It also
scales badly: the vocabulary would grow a term per sector, which is the combinatorial problem this
ADR exists to avoid.

**C. Hand-author a pack per sector, as today.** Rejected as the status quo that produced the
problem: thirteen industries, three distinct plans.

**D. Publication as a status on the template, with "active = newest release".** Rejected twice
over (§4). As a status, rollback is a data edit that destroys the record of what was live. As
"newest wins", undoing a bad v4 requires minting a v5 that exists only to reverse a mistake —
polluting the version history and still losing the record of what was live between the two.
An explicit pointer costs one small table and makes rollback a single write.

**G. Binding the selection to the discovery session, or to the organization.** Rejected. A session
is a browser artifact that may be interrupted or span several sittings; an organization is
assessed repeatedly over years, so binding there erases which knowledge produced which report. An
`Assessment` is the thing with a beginning and an end, and it is what a report cites.

**E. Reuse the ADR 0044 `approver` role.** Rejected. Approving one customer's plan and approving
knowledge for every customer in a sector differ by blast radius; one role for both would let a
plan approver silently change what every future customer is asked.

**F. Generate Arabic and English together.** Rejected (§3). It creates two sources of truth for
one question and no record of which is authoritative.

## Revision history

- 2026-08-07 — Proposed.
- 2026-08-07 — **Accepted with changes** by the product owner. Four amendments applied:
  `Assessment` replaces the session/organization binding (§4, alternative G); the Active Release
  Pointer replaces "newest un-superseded row" (§4, alternative D); reproduction metadata is
  recorded on every release (§6); and Knowledge Freeze makes a released asset immutable including
  its prompt and model (§7). Decision count 6 -> 8; `In Review` added to the release lifecycle so
  a reviewer's queue is computable.
