# ADR 0021: Policy Analyst Agent — deterministic policy-quality review, read-only Tool

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §1, §5, §9, §11, §15, §19, §20; ADR 0006, 0017, 0018, 0019, 0020

## Context

PI-P3's Policy Hunter (ADR-0020) scans *across* a tenant's obligations and policies to find
categorical coverage gaps (which obligations have no policy at all). Policy Analyst (PI-P4,
named alongside Policy Hunter and Policy Builder in ADR-0017's roster) is the complementary,
deeper view: given *one specific* policy, is it actually a *good* policy — complete,
regulator-aligned, internally consistent, and current? This is a quality-review problem, not
a generation problem, so the same reasoning ADR-0020 used against an LLM applies again: a
deterministic, reproducible check is available and preferable to a model's free-form
judgment wherever the check can be expressed as a rule (CLAUDE.md §1).

## Decision

We will:

1. Add `packages/policy-analyst` (`grc_policy_analyst`), depending only on `grc_domain` and
   `grc_tools` — no database library, no LLM SDK, and no dependency on `grc_policy_hunter`
   (a small, self-contained word-overlap helper is duplicated rather than shared across the
   two independent agent packages, consistent with how `grc_regulatory_intelligence` and
   `grc_regulatory_crawlers` already stay decoupled from each other).
2. Implement `quality_engine.review_policy` as a **pure, deterministic** function across four
   dimensions, each produces zero or more `QualityFinding`s (never fabricated — every finding
   traces to an actual keyword absence, a blank field, a real date comparison, or two
   conflicting words found in the text):
   - **Completeness** — a lexical keyword-absence check across the seven required sections
     (purpose, scope, ownership, responsibilities, controls, review cycle, exceptions).
   - **Regulatory alignment** — for every confirmed obligation whose *title* is relevant to
     this policy (a coarse Jaccard filter, so an obligation with nothing to do with this
     policy produces no finding here at all — that is Policy Hunter's problem, not this
     policy's), a **recall** score of the obligation's own significant words against the full
     policy *body* decides `missing_clause` (recall `< 0.25`), `weak_regulatory_coverage`
     (`0.25`–`0.60`, obligation not newer), or `outdated_reference` (`0.25`–`0.60`, obligation
     newer than the policy). Recall, not Jaccard, was chosen deliberately: a long,
     multi-section policy body must not be penalized for containing many other words unrelated
     to one specific obligation — an early calibration against a real "Access Control Policy"
     body scored a clear textual match at Jaccard `0.10` (would misfire as a gap) but recall
     `0.83` (correctly recognized as covered).
   - **Internal consistency** — unclear ownership (the structured `owner_name` field is blank
     or a placeholder like `"TBD"`/`"unassigned"`), ambiguous language (a fixed list of weasel
     phrases: "as appropriate", "where feasible", ...), and conflicting requirements (the same
     *specific* cadence anchor — `"reviewed"`, `"audited"`, `"assessed"`, `"trained"` — stated
     with two different frequency words anywhere in the body). The anchors are deliberately
     specific verb forms, not the bare word "review": an early calibration found "access
     reviews are conducted quarterly" and "this policy is reviewed annually" colliding as a
     false conflict on the generic word "review" even though they describe different
     activities; requiring "reviewed" (not "reviews"/"review") separates them correctly.
   - **Freshness** — the policy itself is stale (untouched over 365 days), or a
     *substantively* covered obligation (recall `>= 0.60`) whose source regulation was
     fetched more recently than the policy was last updated (`policy_older_than_regulation`
     — a weakly-covered-and-newer obligation is `outdated_reference` under alignment instead,
     so each (obligation, policy) pair produces exactly one finding, never two for the same
     underlying signal).
3. Every finding carries the evidence CLAUDE.md §19 requires: `finding_type`, `severity`,
   `evidence` (the concrete text/date that triggered it), `citation` (`"policy:<policy_id>"`
   for policy-internal findings, `"<source_id>#<obligation_id>"` for obligation-linked ones —
   the same citation format ADR-0020 established), `recommendation`, `confidence`, and
   `related_obligation_id` (`None` when the finding isn't tied to one).
4. Implement one Tool (`tools.py`), `review_policy_quality.v1`, `ToolSideEffect.READ_ONLY`
   (structurally `requires_approval=False` — there is nothing to gate). It is the
   anti-corruption boundary (CLAUDE.md §15): it fetches the policy, confirmed obligations, and
   their source documents via `ports.py`'s structural `Protocol`s, translates them into
   `models.py`'s plain value objects, and only then calls `review_policy` — the engine itself
   never touches a database record. An unknown `(tenant_id, policy_id)` raises
   `PolicyNotFoundError`, which the Tool Registry records as a `failed` invocation like any
   other error (CLAUDE.md §19: a rejected call is exactly as auditable as a successful one).
5. Keep `packages/policy-analyst` decoupled from `grc_persistence_web` via
   `PolicyStore`/`ObligationStore`/`RawDocumentStore` — structural `Protocol`s matching
   `grc_persistence_web`'s existing `PolicyRepository`/`RegulatoryObligationRepository`/
   `RegulatoryRawDocumentRepository` shapes exactly. No new persistence code or migration was
   needed.
6. Add `PolicyAnalystAgent` (`agent.py`) as the roster entry: it calls only its one Tool,
   through the Tool Registry, so every invocation is authorized, validated, and
   unconditionally audited exactly like any other Tool call — the same wiring/audit-logging
   guarantee and scope level (tested directly, no `apps/api` HTTP endpoint yet) that PI-P1's
   classifier Tool and PI-P3's Policy Hunter Tools already have.

## Consequences

**Positive**
- Every finding is fully reproducible and evidence-backed: the same policy and obligations
  always produce the same findings, with no hallucination risk and no LLM cost/latency —
  verified by 21 tests asserting exact finding types, not "roughly reasonable" output,
  including two tests that specifically pin down calibration edge cases (the recall-vs-Jaccard
  choice, and the "reviewed" vs. bare "review" anchor specificity) so a future change can't
  silently regress them.
- Zero new dependencies and zero new migrations — entirely additive on top of what
  PI-P1/PI-P2/PI-P3 already persist.
- `PolicyAnalystAgent`/its Tool are structurally incapable of writing anything: the one Tool
  is `READ_ONLY`, and no code path in the package calls an insert/update/approve anywhere.

**Negative / costs**
- The regulatory-alignment recall score and the internal-consistency cadence-conflict
  heuristic are both blunt instruments (word-overlap and keyword co-occurrence, not semantic
  understanding) — they can miss a policy that covers an obligation with entirely different
  vocabulary, or over-flag a coincidental word collision the calibration tests didn't
  anticipate. This is the same trade-off ADR-0020 accepted for Policy Hunter, for the same
  reason: biasing toward surfacing a possible issue for human review is the safer failure mode
  for a compliance tool than silently missing one.
- No `apps/api` HTTP endpoint or scheduled run exists yet — Policy Analyst is a tested
  library, not yet reachable from the workspace UI. That composition is a later, separate
  decision, as it was for Policy Hunter.
- `packages/policy-analyst` duplicates a small Jaccard/tokenizer helper that also exists in
  `packages/policy-hunter` rather than sharing it. Accepted as the cost of keeping the two
  agent packages independently deployable/testable; revisit only if a third package needs the
  same helper and the duplication becomes a real maintenance burden.

## Alternatives considered

- **Use an LLM to judge policy quality.** Rejected for the same reason ADR-0020 rejected it
  for Policy Hunter: CLAUDE.md §1 prefers a reproducible check over a model's free-form guess
  wherever one is available and sufficient, and every dimension here (section presence, a
  blank field, a date comparison, a word collision) is expressible as a deterministic rule.
- **Share a `similarity`/`matching` utility module between `grc_policy_hunter` and
  `grc_policy_analyst`.** Considered and rejected for this phase: it would create a
  cross-dependency between two otherwise-independent agent packages for a ~15-line helper.
  Revisit if a third consumer appears.
- **Use symmetric Jaccard for regulatory-alignment coverage, matching Policy Hunter's title/
  summary comparison exactly.** Rejected after calibration: Policy Hunter compares short
  texts (title + summary) where Jaccard is appropriate, but Policy Analyst compares an
  obligation against a *whole, multi-section policy body* — Jaccard's union term punishes
  length, understating genuine coverage. A recall score (obligation-token-focused) was
  calibrated instead and is documented in the module docstring and tests.
- **Auto-fix a detected issue (e.g. auto-insert a missing section).** Explicitly out of
  scope: Policy Analyst's job is to find and evidence issues, not resolve them — resolving
  them is Policy Builder's job (a future, separate phase per ADR-0017), which will itself
  remain human-gated per CLAUDE.md §1/§9.
