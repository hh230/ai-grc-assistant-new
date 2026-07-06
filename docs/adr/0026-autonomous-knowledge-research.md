# ADR 0026: Autonomous Knowledge Research (KI-P2) — curated trusted-source planning, reused HTTP crawling, and grounded discovery with zero new Tools

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §1, §5, §7, §9, §11, §12, §13, §15, §16, §19, §20; ADR 0006, 0018, 0019,
  0025

## Context

ADR-0025 (Knowledge Intelligence KI-P1) built a Knowledge Question Generator, a deterministic
Knowledge Gap Detector, and a `KnowledgeDiscoveryEngine` that synthesizes a candidate
`KnowledgeItem` from one question and one *already-fetched* `SourceExcerpt`. It named its
largest limitation explicitly: "no live trusted-source fetching... a human (or a future
adapter) must supply the excerpt today," and pointed at the intended fix — reuse
`grc_regulatory_crawlers`, not build a second crawler. This phase (Knowledge Intelligence
KI-P2) closes that gap: when the Gap Detector reports a `MISSING` or `OUTDATED` question
(e.g. "what clauses should exist in a technology vendor contract?"), the system should be able
to decide where trustworthy information may exist, retrieve it, and hand the result to the
unmodified KI-P1 pipeline — without ever scraping the open web or trusting an uncurated site.

The governing constraint carried forward from ADR-0025 is unchanged and, if anything, more
load-bearing here: "do not use random blogs, unsourced AI answers, or unverifiable
information." A general web-search adapter would make "decide where trustworthy information
may exist" an open-ended, uncurated question — exactly what ADR-0025 already rejected for the
question catalog itself ("a fixed, reviewable file is auditable in a way a runtime-generated
list is not"). The design question this phase had to resolve was therefore not "should we
crawl" but "how do we let the system search *only* within sources a human has already vetted,
and only for documents actually relevant to the question, before ever spending an LLM call."

## Decision

We will, mapping the requested research pipeline onto the codebase's existing seams:

**1. Determine what information it needs — reuse, not reinvent.** The "what" is already a
`KnowledgeQuestion` from KI-P1's catalog; this phase adds nothing here. `grc_knowledge_research`
(a new pure package, zero third-party dependencies beyond the already-dependency-free
`grc_knowledge_intelligence`) treats the question as the unit of work throughout.

**2. Decide where trustworthy information may exist — a curated allowlist, ordered by
authority, never an open search.** A new `/trusted-sources/<jurisdiction>/<source_id>.json`
directory (the same "frameworks are data" pattern, CLAUDE.md §13, `/regulatory-sources` and
`/knowledge-catalog` already established) tags each `TrustedSource` with the `KnowledgeDomain`s
it covers. `grc_knowledge_research.planning.build_research_plan` is a **pure, deterministic**
function — no LLM — that filters this catalog to the question's domain and orders matches by a
fixed authority ranking (law/regulation and government regulators checked before official
guidance). A domain with nothing cataloged yields an empty plan — reported as insufficient
evidence later, never guessed at from an unverified source. The initial catalog reuses the six
Saudi regulators `/regulatory-sources/sa` already crawls for Regulatory Intelligence (real,
already-verified URLs), tagged by mandate; it deliberately does not invent unverified
standards-body URLs for domains like Contracts or Vendor Management — see Consequences.

**3. Search/retrieve relevant materials — the reused HTTP crawler, plus a cheap relevance
filter before any LLM call.** `grc_knowledge_research_adapters.HttpResearchCrawler` implements
the pure package's one port (`ResearchCrawlerPort`) using `grc_regulatory_crawlers`'s
already-built primitives — `HttpFetcher`, `RobotsChecker`, `PoliteRateLimiter`,
`discover_links`/`html_to_text`, `pdf_to_text` — exactly the reuse ADR-0025 asked for, never a
second crawler. It is not `HttpRegulatoryCrawler` itself, whose `discover`/`fetch` signatures
are coupled to `grc_regulatory_intelligence`'s own domain types; an anti-corruption translation
(CLAUDE.md §15) converts its `DiscoveredDocumentRef` into this package's own generic type at
the boundary. Before any document is fetched, `grc_knowledge_research.relevance.rank_refs`
scores a source's discovered links against the question by simple word overlap — deterministic,
free, and enough to separate "clearly about vendor contracts" from "clearly about something
else" without an embedding model or a network call.

**4. Validate source quality — structural, not a judgment call at query time.** A source is
never a research candidate unless it already appears in the curated catalog *and* its
`source_type` is one of `TrustedSourceType`'s five members — the same "no random blogs" type
enforcement ADR-0025 gave `TrustedSource` itself, now also gating which sources are even
discoverable. There is no code path that fetches or grounds an answer from a URL outside this
allowlist.

**5. Extract useful knowledge — the unmodified KI-P1 engine, reused, not duplicated.**
`grc_knowledge_research.coordinator.ResearchCoordinator` walks a plan's sources and ranked
documents, calling `KnowledgeDiscoveryEngine.discover` (from `grc_knowledge_intelligence`,
**zero changes**) per candidate excerpt. Its extractor port is, at composition time,
`LlmKnowledgeExtractor`, which already calls `synthesize_knowledge_answer` through the Tool
Registry — so **every synthesis attempt this coordinator triggers is already authorized,
validated, and unconditionally audited**, including rejected/ungrounded ones, exactly like any
other Tool invocation (CLAUDE.md §19). **This phase adds no new Tool.** A source-discovery or
document-fetch failure is recorded as an attempt and isolated (CLAUDE.md §16, fail-safe) —
never aborts the rest of the plan; a bounded budget (`max_sources`, `max_documents_per_source`,
an early-stop confidence) keeps a single research run's cost predictable (CLAUDE.md §7).

**6. Store structured knowledge with evidence — the unmodified KI-P1 upsert, wired end to
end.** `grc_knowledge_research_adapters.KnowledgeGapResearchRunner` mirrors
`RegulatoryCrawlerRunner`'s role exactly: it loads the current knowledge base through a
structural `KnowledgeItemStore` port (satisfied by `grc_persistence_web.KnowledgeItemRepository`
without a direct dependency on it or any DB library), runs `detect_gaps` (unmodified), researches
every actionable gap, and stores every grounded result via the same idempotent-on-`version_hash`
`upsert` ADR-0025 already built and proved never resets a human's prior verification. One
question's research or storage failure is isolated and reported, never blocking another's.
`ResearchResult.version_hash` is computed once, by the coordinator, at the moment the winning
excerpt is still in hand (`compute_version_hash`, reused unmodified) — neither `KnowledgeItem`
nor the result otherwise retains raw excerpt text a storage layer could recompute it from later.

**7. No new Tool; the runner is not one either.** Every real LLM call funnels through the
already-registered `synthesize_knowledge_answer`. `KnowledgeGapResearchRunner` itself is not a
Tool for the same reason `RegulatoryCrawlerRunner` is not: it is multi-step, network-bound, and
potentially long-running — Workflow-Engine-shaped batch orchestration (CLAUDE.md §5), not a
single request/response capability the six-callers contract (CLAUDE.md §9) is asking for.

## Consequences

**Positive**
- Closes ADR-0025's largest named gap using the exact reuse path it prescribed:
  `grc_regulatory_crawlers`'s primitives, not a second crawler; `KnowledgeDiscoveryEngine` and
  `compute_version_hash`, not a second extraction engine; `KnowledgeItemRepository.upsert`, not
  a second storage path.
- "Do not use random blogs" now holds at two independent layers: `TrustedSource` still cannot
  be constructed from an unclassified type (ADR-0025), and now a source cannot even become a
  research candidate unless it is present in the curated `/trusted-sources` catalog.
- Every synthesis attempt a research run makes — grounded, rejected, or never reached because
  an earlier candidate already answered confidently — is Tool-Registry-audited for free,
  because the extraction step is reused unchanged rather than reimplemented.
- Zero new architectural patterns: the pure-engine/adapters package split, the port +
  Tool-audited-adapter seam, the data-as-config catalog, and the runner-ties-everything-together
  shape all mirror `grc_regulatory_intelligence`/`grc_regulatory_crawlers` line for line where
  the shapes coincide.
- 37 new tests (16 pure engine — planning, relevance, coordinator; 21 adapters — crawler,
  catalog loader, runner), all deterministic against fakes; nothing requires network, an API
  key, or a database to pass.

**Negative / costs**
- **The trusted-source catalog is narrow and Saudi-regulator-heavy.** It reuses the six sources
  `/regulatory-sources/sa` already crawls (real, already-verified URLs) rather than inventing
  unverified international standards-body URLs (ISO, NIST, ...) for domains like Contracts,
  Vendor Management, Internal Controls, Audit, or Policies & Procedures. A question in one of
  those domains today yields an empty plan and an `insufficient_evidence` result — a correct,
  honest outcome, but not yet a useful one for several of KI-P1's own 11 domains. Growing this
  catalog is ongoing editorial work (add a reviewed JSON file), the same posture ADR-0025 took
  for the question catalog's own narrowness.
- **No scheduling.** `KnowledgeGapResearchRunner` exists and is tested but nothing calls it on a
  cadence — no `apps/worker` cron job, per the same scope boundary ADR-0019 held regulatory
  crawling to before its own scheduling phase.
- **No `apps/api` endpoint, no UI, no consumer wiring.** Explicitly out of scope for this phase,
  matching ADR-0025's own boundary; Policy Hunter/Analyst/Builder still do not read from
  `knowledge_items`.
- **Relevance ranking is a cheap heuristic, not semantic search.** Word overlap can miss a
  document whose title doesn't share vocabulary with the question even though its content
  answers it. Acceptable for now because the LLM extraction step still runs per candidate and
  correctly reports "not grounded" rather than guessing; a smarter ranker is a drop-in
  replacement behind the same pure function later if the catalog grows large enough to need one.

## Alternatives considered

- **Wire a general web-search API (Google/Bing Custom Search) for open-ended source
  discovery.** Rejected: this reintroduces exactly the "random blogs, unsourced AI answers,
  unverifiable information" ADR-0025 ruled out, just one layer removed (a search engine
  choosing what's "trustworthy" instead of an LLM). If the curated catalog's coverage proves
  too narrow in practice, the fix is to grow the catalog by PR, not to add an uncurated
  discovery path.
- **Reuse `HttpRegulatoryCrawler` directly instead of a new `HttpResearchCrawler`.** Rejected:
  its `discover`/`fetch` signatures take `RegulatorySource`/return
  `RegulatoryDocumentInput`/`DiscoveredDocumentRef` — types that belong to the Regulatory
  Intelligence bounded context and carry no meaning for a `TrustedSource`. The primitives one
  level down (`HttpFetcher`, `RobotsChecker`, `PoliteRateLimiter`,
  `discover_links`/`html_to_text`, `pdf_to_text`) are the genuinely reusable, context-free part;
  `HttpResearchCrawler` is a thin, parallel adapter built from those same primitives, per
  ADR-0025's own instruction to reuse the crawler infrastructure, not its regulatory-specific
  orchestration.
- **Give the Research Coordinator its own LLM-backed relevance-classification step** (an extra
  model call per candidate document, before extraction). Rejected: `KnowledgeDiscoveryEngine`
  already reports "not grounded" (confidence 0, translated to `None`) when an excerpt doesn't
  address the question — a second classification call would duplicate that judgment at
  additional cost and latency for no new information. A cheap, deterministic word-overlap
  ranking is enough to order *which* candidate gets that judgment first.
- **Make `ConductKnowledgeResearchTool` (the whole per-question research run) a registered
  Tool.** Rejected: unlike a single bounded capability (`retrieve_evidence`,
  `map_frameworks`), one research run is inherently multi-step, network-bound, and of
  unpredictable duration — the same reasoning that already keeps
  `RegulatoryCrawlerRunner.run()` out of the Tool Registry. The one real LLM step inside it is
  already a Tool; wrapping the whole run in a second one would audit the same synthesis calls
  twice for no benefit.
- **Let a changed answer's storage go through a human approval gate before it lands as
  `discovered`.** Rejected, consistent with ADR-0025 §6: a `DISCOVERED` item is not yet
  trusted — nothing consumes it as fact until a human explicitly verifies it via
  `set_verification_status`. Gating the write itself would duplicate that safeguard at the
  wrong layer.
