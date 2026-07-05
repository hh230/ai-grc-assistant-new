# ADR 0018: Regulatory Intelligence engine — pure obligation pipeline, Tool-audited LLM
classification, and platform-scope storage

- Status: Accepted
- Date: 2026-07-05
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §5, §9, §12, §13, §16, §19, §20; ADR 0006, 0007, 0012, 0017

## Context

Policy Intelligence PI-P0 (ADR-0017) stood up the real Tool Registry and the
`packages/persistence-web` bridge to apps/web's live Postgres schema, but had nothing yet
feeding it real regulatory content. Policy Hunter (a later phase) needs *structured*
obligations — not raw regulatory text — to match against internal policy coverage. Someone
has to turn a fetched regulation into atomic, classified `RegulatoryObligation` rows first.

This is squarely a Framework-Engine-shaped problem (CLAUDE.md §13: frameworks/obligations are
data, never hardcoded into control flow) crossed with a RAG-shaped problem (CLAUDE.md §12:
grounding, citations, confidence) — but for *obligation extraction*, not question answering.
The existing `packages/extraction` / `packages/extraction-adapters` pair (the Knowledge
Extraction Engine) solves a related but heavier problem (multi-stage document ingestion into
the `packages/domain` Knowledge Database) that is itself gated on the still-unresolved
M5↔M3 persistence re-alignment (ADL-0008) and not wired to apps/web's live schema at all. PI-P1
needs a small, direct pipeline that plugs into the PI-P0 runtime (Tool Registry,
`grc_persistence_web`) today, without reopening that unrelated decision or importing its debt.

## Decision

We will:

1. Add `packages/regulatory-intelligence` (`grc_regulatory_intelligence`): a pure domain
   pipeline with **zero external dependencies** (stdlib only — not even `grc_domain`). It
   defines the classification vocabulary (`ObligationType`, `ControlDomain`, `Severity`,
   `ClassificationStatus`), the value objects (`RawRegulatoryDocument`, `ObligationCandidate`,
   `ObligationClassification`, `ClassifiedObligation`), two ports
   (`ObligationExtractorPort`, `ObligationClassifierPort`), and the coordinator
   `RegulatoryIntelligenceEngine` that drives one document through split-then-classify,
   deterministically. A classifier failure for one candidate is isolated (CLAUDE.md §16: fail
   safe, not open) — the obligation is still recorded via
   `ObligationClassification.unclassified()`, `pending_review`, zero confidence, rather than
   dropped or guessed at, and the run continues. Every obligation is created `pending_review`
   — this package never auto-confirms an AI classification (CLAUDE.md §1).
2. Add `packages/regulatory-intelligence-adapters`, depending on the engine, `grc_domain`,
   `grc_tools`, and `grc_llm`: `RegulatoryConnectorPort` plus two reference connectors
   (`StaticRegulatoryConnector` for offline/tests, `HttpRegulatoryConnector` on stdlib
   `urllib`); `RuleBasedObligationExtractor` (a deterministic clause/sentence splitter with
   offset-accurate spans); the versioned prompt `classify_regulatory_obligation.v1`; and
   `ClassifyRegulatoryObligationTool` — a first-class `grc_tools.Tool` (read-only, typed
   Pydantic I/O, pydantic-validated against the classification vocabulary, rejecting
   malformed/unsupported LLM output before it ever becomes a classification) plus
   `LlmObligationClassifier`, the `ObligationClassifierPort` adapter that invokes that Tool
   **through the Tool Registry** — so every classification call is authorized, validated, and
   unconditionally audited exactly like any other Tool invocation (CLAUDE.md §19), never a raw
   LLM SDK call from business logic (CLAUDE.md §7).
3. Add two tables via `apps/web/lib/db/migrations/0016_regulatory_intelligence.sql`:
   `regulatory_raw_documents` and `regulatory_obligations`. Both are **platform-scope, no
   `tenant_id`** — a regulation is shared reference data every tenant's Policy Hunter draws
   from, exactly like the Framework Engine's framework definitions and like
   `ai_tool_invocations.tenant_id = NULL` platform runs (0013 already named this subsystem in
   advance). `regulatory_raw_documents.content_hash` and `regulatory_obligations.version_hash`
   are unique, giving both tables an idempotent upsert key. A DB check constraint enforces
   that a sub-0.5-confidence classification can never be created anything but
   `pending_review`.
4. Add `RegulatoryRawDocumentRepository` and `RegulatoryObligationRepository` to
   `packages/persistence-web` (the one bridge to apps/web's schema, per ADR-0017) — both
   `upsert`-on-conflict, so re-running a connector fetch or the classification pipeline is a
   no-op rather than a duplicate row.
5. Wire nothing into `apps/api`/`apps/worker` yet, and build no review UI. Policy Hunter
   matching stays out of scope. This phase only makes the pipeline real and testable
   end-to-end (connector → engine → repositories) — composing it into a scheduled job or an
   Orchestrator mission is a later phase's decision.

## Consequences

**Positive**
- A working, tested, audited pipeline from raw regulatory text to structured, classified
  obligations — Policy Hunter has real data to consume when that phase starts.
- The pure engine (`grc_regulatory_intelligence`) has zero dependencies, so its 7 unit tests
  run with no infrastructure at all, and any future adapter (a smarter splitter, a different
  LLM provider) plugs in behind the same two ports without touching orchestration.
- Every classification is audited via the real Tool Registry (PI-P0), for free — no bespoke
  logging path for this subsystem.
- No parallel database, no parallel migration path: one more feature landing on apps/web's
  live schema through `grc_persistence_web`, consistent with ADR-0017.

**Negative / costs**
- The rule-based `RuleBasedObligationExtractor` is a simple numbered-clause/sentence splitter,
  not a legal-grade clause parser — it will occasionally over- or under-split. Acceptable for
  this phase because every obligation is `pending_review` regardless; a smarter extractor is a
  future adapter swap, not an engine change.
- `packages/regulatory-intelligence`'s "no dependency" rule means it defines its own
  value objects rather than reusing `grc_domain`'s. This is a deliberate boundary (mirroring
  why `packages/persistence-web` targets apps/web's schema instead of `packages/persistence`'s
  — see ADR-0017): it keeps this new pipeline decoupled from the separate, ADL-0008-gated
  Knowledge Extraction Engine track, at the cost of some structural duplication between the
  two (e.g. both have their own notion of a document/candidate/confidence).
- Nothing yet calls this pipeline in production (no scheduled job, no Orchestrator mission) —
  it is fully built and tested but must be composed by a future phase.

## Alternatives considered

- **Extend `packages/extraction`/`packages/extraction-adapters` (the Knowledge Extraction
  Engine) instead of a new package.** Rejected: that engine targets `packages/domain`'s
  Knowledge Database, which is gated on the unresolved M5↔M3 persistence re-alignment
  (ADL-0008) and has no binding to apps/web's live schema. Building PI-P1 there would import
  that unrelated debt and still need a second bridge to apps/web afterward.
- **Let the classifier adapter call `grc_llm.ChatModel` directly, bypassing the Tool
  Registry.** Rejected: CLAUDE.md §7/§19 require every AI action to be auditable via the same
  path regardless of caller; a direct call would be a second, un-audited way to invoke an LLM,
  undermining the Registry ADR-0017 just implemented.
- **Auto-confirm high-confidence classifications instead of always `pending_review`.**
  Rejected for this phase: CLAUDE.md §1 requires human-in-the-loop by default for consequential
  AI output, and a classification feeding policy generation is consequential. Revisit only
  alongside an explicit human-review workflow, not as a side effect of this phase.
- **Give `regulatory_raw_documents`/`regulatory_obligations` a `tenant_id`.** Rejected:
  regulations are reference data shared across tenants, not tenant-owned; a per-tenant copy
  would duplicate identical rows across thousands of organizations for no benefit, and
  contradicts how `ai_tool_invocations` and the Framework Engine already model this class of
  data.
