# grc-regulatory-intelligence-adapters

Concrete, outer-infrastructure adapters for the Regulatory Intelligence engine
(`grc_regulatory_intelligence`), per CLAUDE.md §5's dependency direction: this package
depends on the pure engine and implements its ports; the engine never imports this package.

- `connectors.py` — `RegulatoryConnectorPort` (fetch one regulatory source) plus two
  reference implementations: `StaticRegulatoryConnector` (deterministic, offline — used by
  tests and any no-egress dev flow) and `HttpRegulatoryConnector` (a minimal stdlib
  `urllib`-based fetcher; swap for a richer client when a real regulator feed is onboarded).
- `extraction.py` — `RuleBasedObligationExtractor`: a deterministic `ObligationExtractorPort`
  that splits on numbered regulatory clauses (falling back to sentence boundaries), with
  accurate character offsets into the source document.
- `prompts.py` — the versioned `classify_regulatory_obligation.v1` prompt (CLAUDE.md §22:
  prompts are versioned artifacts, never inline in business logic).
- `classification.py` — `ClassifyRegulatoryObligationTool` (a first-class `grc_tools.Tool`:
  typed Pydantic I/O, read-only side effect, calls the provider-agnostic `ChatModel`, rejects
  malformed/unsupported LLM output before it ever becomes a classification) and
  `LlmObligationClassifier` (the `ObligationClassifierPort` adapter that invokes that Tool
  **through the Tool Registry** — so every classification call is authorized, validated, and
  unconditionally audited exactly like any other Tool invocation, CLAUDE.md §19).

Nothing here writes to a database — persistence lives in `grc_persistence_web`
(`RegulatoryRawDocumentRepository`, `RegulatoryObligationRepository`), which is the one bridge
to apps/web's live Postgres schema (ADR-0017, ADR-0018).
