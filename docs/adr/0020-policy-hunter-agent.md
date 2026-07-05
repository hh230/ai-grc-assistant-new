# ADR 0020: Policy Hunter Agent — deterministic coverage-gap detection, read-only Tools

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §1, §5, §9, §11, §15, §19, §20; ADR 0006, 0017, 0018, 0019

## Context

PI-P1/PI-P2 built the pipeline that turns regulator publications into confirmed, classified
`RegulatoryObligation`s. Nothing yet compares that against a tenant's actual policies. Policy
Hunter (named in ADR-0017 as part of the Policy Intelligence roster, alongside a future Policy
Analyst and Policy Builder) is that comparison: read confirmed obligations, read one tenant's
policies, and report where coverage is missing, partial, or stale.

This is explicitly a read-only reporting capability — CLAUDE.md §1/§9 require a human to
decide before anything consequential happens, and Policy Hunter has no consequential action to
propose at all: it produces a list of findings, nothing more. The interesting design question
was not "should this write" (it never does), but "how should a gap be detected, and how
honest can a confidence score be." An LLM could compare an obligation's text to a policy's and
render a judgment, but that judgment would be exactly the kind of thing CLAUDE.md §1 says to
avoid guessing at when a better option exists — and a better option exists here: obligation
and policy text can be compared directly by their shared vocabulary, deterministically.

## Decision

We will:

1. Add `packages/policy-hunter` (`grc_policy_hunter`), depending only on `grc_domain` and
   `grc_tools` — no database library, no LLM SDK. Its matching engine (`matching.py`,
   `scan_coverage`) is a **pure, deterministic** function: a word-overlap (Jaccard) similarity
   between one obligation's `suggested_policy_title`+text and each policy's `title`+`summary`,
   with the highest score classified into one of four `GapCategory`s (`enums.py`):
   - `unmapped_regulatory_obligation` — best score is exactly `0.0` (shares nothing with any
     policy at all, including when the tenant has none).
   - `missing_required_policy` — a faint signal exists (`0.0 < score < 0.15`) but nothing
     substantively addresses the obligation.
   - `incomplete_coverage` — a related policy exists (`0.15 <= score < 0.30`) but doesn't
     clearly cover the obligation.
   - `outdated_policy` — a substantive match (`score >= 0.30`) whose policy was last updated
     *before* the obligation's source regulation was last fetched (i.e. the regulation changed
     since).
   - Otherwise: no finding — the obligation is covered. Thresholds were calibrated against
     representative obligation/policy text pairs (see the module docstring and tests), biased
     conservative (lower thresholds) because under-claiming coverage is the safer failure mode
     for a compliance tool than over-claiming it.
   A finding's `confidence` is a property of this algorithm (the match score itself, or `1 -
   score` for the two "nothing found" categories) — never a fabricated model confidence.
2. Every finding carries the evidence CLAUDE.md §19 requires: `source_id`/`source_url` (the
   obligation's originating regulator/document), a `citation` (`"<source_id>#<obligation_id>"`),
   the `confidence` score, and `matched_policy_id`/`matched_policy_title` (`None` when nothing
   matched at all).
3. Implement two Tools (`tools.py`), both `ToolSideEffect.READ_ONLY` (which structurally sets
   `requires_approval=False` — CLAUDE.md §9's rule that consequential tools always gate;
   these simply have nothing to gate): `list_applicable_obligations.v1` (confirmed obligations,
   optionally filtered by control domain) and `scan_policy_coverage_gaps.v1` (the full gap
   scan for one tenant). Each Tool is the anti-corruption boundary (CLAUDE.md §15): it fetches
   concrete records via `ports.py`'s structural `Protocol`s, translates them into
   `models.py`'s plain value objects, and only then calls `scan_coverage` — the engine itself
   never touches a database record.
4. Keep `packages/policy-hunter` decoupled from `grc_persistence_web` (and any DB library)
   via `ObligationStore`/`RawDocumentStore`/`PolicyStore` — structural `Protocol`s matching
   `grc_persistence_web`'s existing `RegulatoryObligationRepository`/
   `RegulatoryRawDocumentRepository`/`PolicyRepository` shapes exactly, the same decoupling
   pattern `grc_regulatory_crawlers.runner` established (ADR-0019). No new persistence code or
   migration was needed — every read this phase needs already exists.
5. Add `PolicyHunterAgent` (`agent.py`) as the roster entry: it calls only its two Tools,
   through the Tool Registry, so every invocation is authorized, validated, and
   unconditionally audited exactly like any other Tool call (CLAUDE.md §11, §19) — the same
   wiring/audit-logging guarantee PI-P1's classifier Tool already has, at the same scope
   level: proven via the Tool Registry and tested directly (CLAUDE.md §9's "Tests" caller),
   with no `apps/api` HTTP endpoint added in this phase (PI-P1's `ClassifyRegulatoryObligationTool`
   was never wired into `apps/api`'s `web_runtime.py` either — this keeps the same boundary).

## Consequences

**Positive**
- Coverage-gap findings are fully reproducible: the same obligations and policies always
  produce the same findings, with no hallucination risk and no LLM cost/latency — verified by
  tests that assert exact categories and confidence scores, not "roughly reasonable" output.
- Zero new dependencies (no LLM SDK, no database library) and zero new migrations — the
  entire capability is additive on top of what PI-P1/PI-P2 already persist.
- `PolicyHunterAgent`/its Tools are structurally incapable of writing a policy: both Tools are
  `READ_ONLY`, and no code path in the package calls an insert/update anywhere.

**Negative / costs**
- Word-overlap similarity is a blunt instrument: it can miss a policy that covers an
  obligation using different vocabulary (a false "gap"), and can over-match a policy that
  happens to share vocabulary without truly addressing the obligation (a false "covered").
  The chosen thresholds bias toward flagging gaps rather than missing them, which is the safer
  direction for a compliance tool but means some findings will need a human's judgment to
  dismiss — exactly the human-in-the-loop posture CLAUDE.md §1 asks for, not a defect to
  "fix" by adding an LLM.
- `outdated_policy` detection compares the *source document's fetch time* to the *policy's
  last update* — it does not know whether the fetched document actually contains a substantive
  change (PI-P2's change detection already filters to changed content before an obligation is
  (re)classified, but a cosmetic edit could still trigger this). Acceptable for this phase;
  refining it is future work on PI-P2's change-detection granularity, not this ADR.
- No `apps/api` HTTP endpoint or scheduled run exists yet — Policy Hunter is a tested library,
  not yet reachable from the workspace UI. That composition is a later, separate decision.

## Alternatives considered

- **Use an LLM to compare obligation and policy text.** Rejected: CLAUDE.md §1 prefers "I
  don't know" over guessing, and a deterministic comparison is available and sufficient here —
  an LLM would add cost, latency, non-determinism, and hallucination risk for a task that
  doesn't need free-form generation, only a similarity judgment.
- **Depend on `grc_persistence_web` directly instead of structural Protocols.** Rejected for
  the same reason ADR-0019 rejected it for the crawler runner: a comparison/reporting library
  should not need a Postgres-specific adapter package as a hard dependency.
- **Distinguish `missing_required_policy` from `unmapped_regulatory_obligation` by "does the
  tenant have any policy at all" instead of per-obligation score.** Rejected: a blanket,
  tenant-level signal would classify every obligation identically for a tenant with few
  policies, even when some of those policies are clearly unrelated to a given obligation. A
  per-obligation `best_score == 0.0` check is a more precise, still fully deterministic signal.
- **Auto-generate a policy draft when a gap is found.** Explicitly out of scope: Policy
  Hunter's job is to find gaps, not close them — drafting is Policy Builder's job (a future,
  separate phase per ADR-0017), which will itself remain human-gated per CLAUDE.md §1/§9.
