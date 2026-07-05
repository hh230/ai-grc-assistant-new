# grc-regulatory-intelligence

The Regulatory Intelligence engine (Policy Intelligence PI-P1, CLAUDE.md §12-13): the pure
domain pipeline that turns a raw regulatory document into structured, classified
`RegulatoryObligation`s for the Policy Hunter agent to consume later.

Flow (CLAUDE.md §5 layering — this package is the pure core; adapters are outer infrastructure):

```
Connector → raw regulatory document → RegulatoryIntelligenceEngine
              (split into atomic obligations → classify each obligation)
            → ClassifiedObligation[] → (persisted by grc_persistence_web) → Policy Hunter
```

- `enums.py` — `ObligationType`, `ControlDomain`, `Severity`, `ClassificationStatus`: the
  stable classification vocabulary. These are *classification categories*, not a framework's
  own structure — no framework name is hardcoded (CLAUDE.md §13).
- `artifacts.py` — immutable value objects: `RawRegulatoryDocument`, `ObligationCandidate`,
  `ObligationClassification`, `ClassifiedObligation`, `RegulatoryIntelligenceResult`.
- `ports.py` — `ObligationExtractorPort` (splits a document into atomic obligation
  candidates) and `ObligationClassifierPort` (classifies one candidate). Concrete adapters
  (rule-based splitter, LLM classifier) live in `grc_regulatory_intelligence_adapters` and
  implement these ports without this package ever importing them back.
- `engine.py` — `RegulatoryIntelligenceEngine`: drives one document through extraction then
  classification, deterministically and fail-safe. A classifier failure for one candidate
  never aborts the run — CLAUDE.md §1/§16 ("fail safe, not open"): the obligation is still
  recorded, flagged `pending_review` with zero confidence, rather than silently dropped or
  guessed at.

**No external dependencies.** This package imports nothing but the Python standard library —
not `grc_domain`, not `pydantic`, not an LLM SDK. That is what lets the engine be tested with
zero infrastructure and lets AI-assisted or rule-based adapters plug in later without coupling
the engine to either.

Every obligation is created `pending_review` — Regulatory Intelligence never auto-confirms an
AI classification (CLAUDE.md §1: human-in-the-loop by default). Confirming or rejecting an
obligation is a future human-gated action, out of scope for PI-P1.
