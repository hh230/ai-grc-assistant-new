# grc-knowledge-research

Autonomous Knowledge Research (Knowledge Intelligence KI-P2): the pure pipeline that closes
the gap ADR-0025 named as KI-P1's largest limitation — "no live trusted-source fetching" —
by planning, ranking, and coordinating grounded research across a curated trusted-source
catalog, so a `GapFinding` can become a researched `KnowledgeItem` without a human supplying
the excerpt by hand.

Flow (CLAUDE.md §5 layering — this package is the pure core; the concrete Tool-audited HTTP
crawler and catalog loader are outer infrastructure, in `grc_knowledge_research_adapters`):

```
KnowledgeQuestion + curated CatalogedSource[] → planning.build_research_plan → ResearchPlan
ResearchPlan + ResearchCrawlerPort + KnowledgeDiscoveryEngine → ResearchCoordinator.research
  → ResearchResult (a KnowledgeItem if grounded, plus the full attempt trail)
```

- `enums.py` — `AttemptOutcome` (grounded/not_grounded/fetch_failed/discovery_failed),
  `ResearchStatus` (found/insufficient_evidence).
- `models.py` — `DiscoveredDocumentRef`, `CatalogedSource` (a `TrustedSource` tagged with the
  `KnowledgeDomain`s it covers), `ResearchStep`/`ResearchPlan`, `ResearchAttempt`,
  `ResearchResult`. Reuses `grc_knowledge_intelligence`'s own `TrustedSource`,
  `KnowledgeQuestion`, `SourceExcerpt`, and `KnowledgeItem` rather than redefining them.
- `planning.py` — `build_research_plan`: **pure, deterministic**, no LLM. "Decide where
  trustworthy information may exist" is a curated allowlist match (catalog entries tagged
  for the question's domain), ordered by a fixed authority ranking (law/regulation and
  government regulators before official guidance) — never an open web search and never a
  model's guess at whether some arbitrary site is trustworthy.
- `relevance.py` — `score_relevance`/`rank_refs`: a cheap, deterministic word-overlap score
  that ranks a source's discovered documents against the question, so only the most
  promising few are ever fetched and sent to the (costly, LLM-backed) extraction step.
- `ports.py` — `ResearchCrawlerPort`: the one abstraction seam. The concrete, polite,
  robots.txt-respecting adapter lives in `grc_knowledge_research_adapters`, built from
  `grc_regulatory_crawlers`'s existing primitives rather than a second crawler.
- `coordinator.py` — `ResearchCoordinator`: walks a plan's sources and documents, calling the
  **unmodified** `KnowledgeDiscoveryEngine.discover` per candidate excerpt, isolating any one
  document's or source's failure (fail-safe, CLAUDE.md §16), and keeping the best-grounded
  result. Bounded by `max_sources`/`max_documents_per_source` (a research budget, CLAUDE.md
  §7) and stops early once a confident-enough answer is found.

**No new Tool.** Every synthesis attempt this coordinator triggers already flows through
`synthesize_knowledge_answer` via `KnowledgeDiscoveryEngine`'s injected
`KnowledgeExtractorPort` — in the adapters package, that port's concrete implementation
(`LlmKnowledgeExtractor`) calls the Tool Registry, so every attempt (including a rejected or
ungrounded one) is already authorized, validated, and audited exactly like any other Tool
invocation. Nothing here bypasses that.

**No external dependencies** beyond `grc-knowledge-intelligence` (itself dependency-free) —
not an HTTP library, not `pydantic`, not an LLM SDK. The same "pure core, zero
infrastructure" posture `grc_knowledge_intelligence`/`grc_regulatory_intelligence` established.

**Not in this package:** the HTTP crawler, the trusted-source catalog loader, persistence,
an `apps/api` endpoint, and any scheduling — see `grc_knowledge_research_adapters` and
ADR-0026.
