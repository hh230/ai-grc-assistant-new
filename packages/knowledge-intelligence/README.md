# grc-knowledge-intelligence

The Autonomous Knowledge Engine (Knowledge Intelligence KI-P1, ADR-0025): the pure domain
pipeline that generates important GRC/compliance/legal questions from a curated catalog,
detects gaps in the stored knowledge base, and coordinates deterministic, trusted-source-
grounded knowledge discovery for a future Policy Hunter/Analyst/Builder/Contract Reviewer to
consume.

Flow (CLAUDE.md §5 layering — this package is the pure core; the concrete Tool-audited LLM
adapter is outer infrastructure):

```
/knowledge-catalog/*.json → question_catalog.build_catalog → KnowledgeQuestion[]
KnowledgeQuestion[] + stored KnowledgeItem[] → gap_detection.detect_gaps → GapFinding[]
one KnowledgeQuestion + one already-fetched SourceExcerpt → KnowledgeDiscoveryEngine
  (via the injected KnowledgeExtractorPort) → candidate KnowledgeItem (status=DISCOVERED)
```

- `enums.py` — `KnowledgeDomain` (11 GRC/legal domains), `TrustedSourceType` (the only five
  source kinds the engine may cite — "do not use random blogs" is structural here, not a
  docstring promise), `VerificationStatus` (`discovered`/`verified`/`needs_review`/`outdated`
  — knowledge is never absolute), `GapStatus` (the gap detector's verdict).
- `models.py` — `KnowledgeQuestion`, `TrustedSource`, `SourceExcerpt`, `KnowledgeAnswer`,
  `KnowledgeItem`, `GapFinding`: plain value objects, independent of `grc_persistence_web`/
  `grc_llm` types.
- `question_catalog.py` — `build_catalog`: loads `/knowledge-catalog/<domain>.json` (data, not
  code — the same pattern `grc_regulatory_intelligence.source_config` established for
  regulators and `grc_framework_engine` for frameworks). The caller resolves and passes in the
  files to load; this module never assumes a repo layout itself.
- `gap_detection.py` — `detect_gaps`/`actionable_gaps`: **pure, deterministic**, no LLM (the
  same choice ADR-0020/0021 made for Policy Hunter/Analyst). Classifies every question against
  the knowledge base's current item as `MISSING` (never researched), `OUTDATED` (explicitly
  flagged, or simply stale by age), `WEAK_CONFIDENCE` (answered, but under the confidence
  bar), or `ANSWERED`.
- `ports.py` — `KnowledgeExtractorPort`: the one abstraction seam. Concrete, Tool-audited,
  LLM-backed implementation lives in `grc_knowledge_intelligence_adapters` and is never
  imported back here. Deliberately **no fetch/research port** in this phase — a
  `SourceExcerpt` (already-fetched text) is an input the caller provides; real trusted-source
  crawling is future work (see ADR-0025).
- `engine.py` — `KnowledgeDiscoveryEngine`/`compute_version_hash`: turns one
  (question, excerpt) pair into a candidate `KnowledgeItem` via the injected port. Every
  discovery starts `VerificationStatus.DISCOVERED` with `last_verified=None` and `version=1`
  — only a human decision, applied later by the storage layer, moves it forward. A failed
  extraction returns `None` rather than guessing (CLAUDE.md §16: fail safe, not open).

**No external dependencies.** This package imports nothing but the Python standard library —
not `grc_domain`, not `pydantic`, not an LLM SDK — the same "pure core, zero infrastructure"
posture `grc_regulatory_intelligence` established.

**Not in this package:** live trusted-source fetching (crawling a regulator site, a standards
body's publication library, ...), an `apps/api` HTTP endpoint, any scheduling/refresh
automation, and any wiring of Policy Hunter/Analyst/Builder to actually read from this
knowledge base. Every one of these is named as explicit future work in ADR-0025, at the same
scope boundary PI-P1 (regulatory obligations, no crawling) and PI-P2 (crawling, added later)
established for Regulatory Intelligence.
