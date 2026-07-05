# ADR 0024: Policy Builder Agent — deterministic starter drafts, zero write path

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §1, §5, §9, §11, §15, §19, §20; ADR 0006, 0017, 0018, 0019, 0020, 0021, 0022

## Context

ADR-0017 named three agents in the Policy Intelligence roster: Policy Hunter (PI-P3, finds
coverage gaps), Policy Analyst (PI-P4, reviews one policy's quality), and Policy Builder —
explicitly deferred in both of those ADRs as "a future, separate phase." Every prior ADR in
this roster was equally explicit about what Policy Builder is *not*: ADR-0020 rejected
"auto-generate a policy draft when a gap is found" as out of scope for Policy Hunter ("Policy
Hunter's job is to find gaps, not close them — drafting is Policy Builder's job"), and
ADR-0021 repeated the same boundary for Policy Analyst. PI-P7 is that phase.

The persistence layer was already built for this moment: `packages/persistence-web`'s
`PolicyRepository.insert_draft` (ADR-0017) and migration `0014_policy_provenance.sql` both
predate this ADR, and the migration's own comment states the intended shape precisely: "An
AI-generated draft is a normal `policies` row (status='draft') that flows through the
existing human-gated workflow unchanged (in_review -> published still requires the `publish`
permission) — these columns only make the authorship and grounding explainable, they do not
change the approval workflow itself."

The one real design question this phase had to answer: policy *drafting* is a generative
task in a way gap-detection and quality-review are not — there is no deterministic algorithm
for "write a good policy." Two shapes were possible: an LLM-backed Tool that generates policy
prose, or a Tool that returns proposed text and performs no write at all, leaving the actual
persistence step to a human acting through machinery that already exists. The explicit
requirement for this phase — human approval before *any* policy change, and no bypassing
Policy Hunter's/Policy Analyst's boundaries — settled it.

## Decision

We will:

1. Add `packages/policy-builder` (`grc_policy_builder`), depending only on `grc_domain` and
   `grc_tools` — no database library, no LLM SDK, and no dependency on `grc_policy_hunter` or
   `grc_policy_analyst` (the same independent-packages choice ADR-0021 made; a small
   `_REQUIRED_SECTIONS`/`_AMBIGUOUS_PHRASES` mirror lives in this package's *tests only*, as a
   local, duplicated constant — never imported from `grc_policy_analyst`'s private module
   internals — so this package can never break because a private symbol elsewhere was
   renamed).
2. Implement `drafting.draft_policy` as a **pure, deterministic template**, not a generator:
   the *Purpose* section quotes the obligation's own text verbatim with a citation; the other
   six sections required by `grc_policy_analyst.quality_engine`'s own completeness check
   (scope, ownership, responsibilities, controls, review cycle, exceptions) are each rendered
   as an explicit `[Human input required: ...]` placeholder. Nothing is invented — the
   *Controls* section names the obligation's `control_domain` as a hint, never a fabricated
   specific control. This means a human who saves the draft unmodified and immediately runs
   Policy Analyst against it sees exactly the placeholders still needing attention, never a
   false "complete" signal — the two agents reinforce each other without either depending on
   the other's code.
3. Implement one Tool (`tools.py`), `draft_policy_from_obligation.v1`,
   `ToolSideEffect.READ_ONLY` (structurally `requires_approval=False` — not because a policy
   draft is unimportant, but because **this Tool has no dependency capable of writing a
   policy anywhere**; it returns proposed text and nothing else). It is the anti-corruption
   boundary (CLAUDE.md §15): it fetches the concrete obligation record via `ports.py`'s
   structural `Protocol`s, translates it into `models.py`'s plain type, and only then calls
   the pure `draft_policy`. Only ever drafts from a `confirmed` obligation —
   `pending_review`/`rejected` obligations are treated as not found (`ObligationNotFoundError`),
   the same evidentiary bar Policy Hunter and Policy Analyst already hold.
4. Keep `packages/policy-builder` decoupled from `grc_persistence_web` via an
   `ObligationStore`/`RawDocumentStore` pair of structural `Protocol`s matching
   `grc_persistence_web`'s existing repositories exactly — the same pattern
   ADR-0019/0020/0021 established. Deliberately **no `PolicyStore` port at all**: Policy
   Builder never reads a tenant's existing policies. Whether an obligation is already covered
   is Policy Hunter's question; whether an existing policy is good enough is Policy Analyst's
   question. Policy Builder answers neither — it only transforms one confirmed obligation
   into a starter draft, which is what "do not bypass Policy Hunter/Analyst boundaries" means
   concretely here.
5. Add `PolicyBuilderAgent` (`agent.py`) as the roster entry: it calls only its one Tool,
   through the Tool Registry, so every invocation is authorized, validated, and
   unconditionally audited exactly like any other Tool call (CLAUDE.md §11, §19) — the same
   wiring/audit-logging guarantee and scope level (tested directly via the Tool Registry, no
   `apps/api` HTTP endpoint yet) that PI-P3's Policy Hunter and PI-P4's Policy Analyst shipped
   at.
6. Enforce "human approval required before any policy change" **by construction**: the only
   path from a `PolicyDraft` to an actual `policies` row is a human explicitly taking the
   proposed `title`/`body` and saving it through the existing, already-shipped policy-authoring
   workflow (`POST /policies` -> `draft`, then the unchanged `submit-for-review` ->
   `approve` -> `publish` lifecycle, still gated by the `publish` permission per ADR-0014).
   No new write path, no new approval mechanism, and no runtime check this phase would have
   had to invent and get right — the guarantee is that Policy Builder is architecturally
   incapable of writing a policy at all.

## Consequences

**Positive**
- The strongest possible form of "human approval required": not a policy this Tool follows,
  but a capability it lacks. There is no configuration, permission, or caller context that
  makes `DraftPolicyFromObligationTool` write anything, because it has no reference to
  anything that could.
- Every draft is fully reproducible and evidence-backed: the same obligation always produces
  the same draft, byte for byte, with no hallucination risk and no LLM cost/latency —
  verified by tests that assert exact body content and placeholder lists, not "roughly
  reasonable" output.
- Zero new dependencies and zero new migrations — `PolicyRepository.insert_draft` and the
  `ai_generated`/`generated_by_tool`/`generation_metadata` columns ADR-0017 already shipped
  are exactly what a future phase wiring this into the save flow will need; nothing about
  this phase requires touching them.
- Cross-agent consistency is achieved without cross-agent coupling: the draft's sections
  mirror Policy Analyst's completeness check by shared convention (both reference the same
  seven named sections from CLAUDE.md-aligned GRC policy structure), not by one package
  importing the other's code.

**Negative / costs**
- The draft is intentionally boilerplate-heavy — six of seven sections are placeholders.
  This is a deliberate GRC safety trade-off, not a shortcoming to fix with an LLM: a draft
  that visibly needs work invites the human review CLAUDE.md §1 requires, whereas a
  polished-looking LLM draft risks being rubber-stamped through the approval workflow without
  genuine scrutiny — the failure mode is precisely the one CLAUDE.md's "trust is the product"
  principle warns against.
- No `apps/api` HTTP endpoint or UI exists yet for this Tool — a human can only reach it
  through the Tool Registry directly (tests) or a future Orchestrator-driven mission. That
  composition is a later, separate decision, exactly as it was for Policy Hunter (PI-P5) and
  Policy Analyst (PI-P6).
- A future phase that wires this into the actual save flow (pre-filling `POST /policies` with
  the proposal) must be careful not to silently skip the human step — e.g. an "auto-save
  draft" button is fine (a human clicked it), but any code path that calls both
  `draft_policy_from_obligation` and `PolicyRepository.insert_draft` without an intervening
  human action would reintroduce exactly the risk this ADR avoids. Not built here, but worth
  naming as the one way this design could be defeated later.

## Alternatives considered

- **An LLM-backed Tool that generates full policy prose.** Rejected for the reason stated in
  Consequences above: a fluent, complete-looking AI draft is *more* likely to be approved
  without real scrutiny than an obviously-incomplete template, which is the opposite of what
  a human-in-the-loop gate is for. It would also reintroduce the cost/latency/non-determinism
  ADR-0020/0021 already rejected for the read-only agents, for a task (a first draft, not a
  final document) that does not need it.
- **Have the Tool itself write the draft to `policies` (status='draft'), relying on
  `requires_approval=True` as the gate.** Rejected: `ToolRegistry.invoke` records
  `requires_human_approval` for audit but does not itself block execution — there is no
  platform-level enforcement mechanism yet that would pause a `CONSEQUENTIAL` tool pending an
  explicit approval decision (that machinery belongs to the Orchestrator/Workflow layer, not
  this phase). Relying on a flag nothing currently enforces would not actually satisfy "human
  approval required before any policy change" as robustly as removing the write path
  entirely.
- **Add a `PolicyStore` port so Policy Builder can check for existing coverage before
  drafting.** Rejected: that is precisely Policy Hunter's `scan_policy_coverage_gaps`
  question. A caller who wants to know whether a gap exists runs Policy Hunter first (already
  exposed via PI-P5/PI-P6) and hands Policy Builder the specific `obligation_id` to draft for
  — Policy Builder trusting that decision, rather than re-deriving it, is what keeps the
  boundary between the two agents real instead of nominal.
- **Share a `_REQUIRED_SECTIONS`/word-overlap helper module with `grc_policy_analyst`.**
  Considered and rejected for the same reason ADR-0021 rejected sharing with
  `grc_policy_hunter`: a cross-dependency between independently-deployable agent packages for
  a small, stable helper is a worse trade than a documented, test-only duplication.
