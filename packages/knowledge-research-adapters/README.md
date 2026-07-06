# grc-knowledge-research-adapters

Autonomous Knowledge Research (Knowledge Intelligence KI-P2): the concrete, outer-layer half
of `grc_knowledge_research` — real HTTP fetching, the curated trusted-source catalog, and the
runner that ties gap detection, research, and storage into one end-to-end pass.

- `crawler.py` — `HttpResearchCrawler`, the reference `ResearchCrawlerPort` implementation.
  Built from `grc_regulatory_crawlers`'s already-built primitives (`HttpFetcher`,
  `RobotsChecker`, `PoliteRateLimiter`, `discover_links`/`html_to_text`, `pdf_to_text`) —
  ADR-0025's explicit future-work note ("reuse `grc_regulatory_crawlers`, not build a second
  crawler") — never its regulatory-specific `HttpRegulatoryCrawler`. Translates
  `grc_regulatory_intelligence`'s `DiscoveredDocumentRef` into this package's own generic
  type at the boundary (an anti-corruption layer, CLAUDE.md §15), and caps how much of a
  fetched page becomes part of an LLM prompt (`DEFAULT_MAX_EXCERPT_CHARS`).
- `trusted_source_catalog.py` — `build_trusted_source_catalog`: loads
  `/trusted-sources/<jurisdiction>/<source_id>.json` (data, not code — the same pattern
  `grc_regulatory_intelligence.source_config` established for regulators) into
  `CatalogedSource`s. A source's `source_type` and `domains` are validated against
  `TrustedSourceType`/`KnowledgeDomain`; a malformed entry fails to load.
- `runner.py` — `KnowledgeGapResearchRunner`: mirrors
  `grc_regulatory_crawlers.RegulatoryCrawlerRunner`'s role exactly. Loads the current
  knowledge base via a structural `KnowledgeItemStore` port, runs `detect_gaps`, researches
  every actionable gap through the injected `ResearchCoordinator`, and stores every grounded
  result via `KnowledgeItemStore.upsert` — the same idempotent-on-`version_hash` upsert
  KI-P1 already built, unchanged. One question's failure (research or storage) is isolated
  and reported, never aborting the rest of the run.

**Not a Tool.** Like `RegulatoryCrawlerRunner`, this runner is multi-step and
network/LLM-bound — batch/Workflow-Engine-shaped, not a single request/response capability.
The one real LLM call it triggers (`synthesize_knowledge_answer`, via whatever
`KnowledgeExtractorPort` the caller composed the injected `ResearchCoordinator`'s
`KnowledgeDiscoveryEngine` with) is already a registered, Tool-Registry-audited capability —
this package adds no new Tool.

**Not in this package:** any `apps/worker` scheduling, an `apps/api` endpoint, and any UI —
explicit future work, at the same scope boundary ADR-0025 held KI-P1 to. See ADR-0026.
