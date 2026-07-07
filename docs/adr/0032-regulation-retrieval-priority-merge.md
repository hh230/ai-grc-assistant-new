# ADR 0032: Retrieval Priority Merge — internal regulations DB -> trusted-source research -> LLM fallback (Proposed, not yet built)

- Status: Proposed — deferred, needs a dedicated design/implementation pass
- Date: 2026-07-07
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §6, §12; ADR 0026, 0030, 0031

## Context

Two independent, now-real sources of grounded regulatory/GRC knowledge exist in this
platform, built in separate phases, and neither currently defers to the other:

1. **KI-P2's trusted-source research pipeline** (ADR-0026): `KnowledgeGapResearchRunner`
   fetches and synthesizes answers live from a curated, authority-ranked source catalog
   (`/trusted-sources`) when a knowledge gap is detected, storing the result in
   `knowledge_items`.
2. **KI-P6/KI-P7's Saudi Regulations Ingestion Pipeline** (ADR-0030, ADR-0031): full official
   regulation text (chapters, articles, amendments) fetched from the Saudi Board of Experts
   legal portal, stored in `regulation_sources`/`regulation_source_versions`/
   `regulation_documents`/`regulation_sections`, gated behind an explicit admin approval
   (KI-P7). As of ADR-0031, approved sections carry real embeddings
   (`regulation_sections.embedding`) — but nothing reads them yet.

Separately, `grc_rag`'s existing retrieval/search (`grc_rag.retrieval`, `grc_rag.semantic`,
`grc_rag.pipeline`) and the AI Agents roster's Knowledge Agent ground answers from whatever
single store each is wired to; there is today no concept of "try source A, then B, then
fall back to C" anywhere in the retrieval path.

The Product Owner named the intended priority explicitly, more than once, across both KI-P6
and this KI-P7 session: **internal regulations DB first (the now-approved, embedded
`regulation_sections` — the platform's own verified official text), trusted-source web
research second (KI-P2's existing pipeline — broader coverage, lower certainty), the LLM's
own general knowledge last (only when neither grounded source has an answer, and clearly
flagged as such)** — but also explicitly instructed, in this same session, that implementing
this merge is **out of scope for KI-P7** and must be tracked as its own follow-up rather than
folded into the approval-workflow-and-embeddings change. This ADR is that tracking: it
records the decision and the shape of the problem, not an implementation.

## Decision (proposed, not implemented)

This is deliberately a **Proposed** ADR — recording intent and the design questions a real
implementation pass must answer, not a binding architecture like every other ADR in this
repo. Nothing described below exists in code yet.

**Rough shape, for whoever picks this up:**

1. **A priority-aware retrieval port**, likely a new `grc_rag` (or a thin layer above it)
   function/class that, given a query, tries sources in order and returns the first grounded
   result above a confidence/relevance threshold, carrying which tier answered (for
   transparency — CLAUDE.md §19, an answer must say which source class it came from, not just
   which document).
2. **Tier 1 — internal regulations DB.** Query `regulation_sections` (only `status =
   'approved'` versions) via its embeddings — the semantic search shape `grc_rag.semantic`
   already establishes for `document_chunks`, applied to a second table. Open question: one
   unified vector search across both `document_chunks` and `regulation_sections`, or two
   separate lookups the merge layer arbitrates? Precedent (`document_chunks`) suggests keeping
   them queryable independently and merging at the application layer, not the SQL layer.
3. **Tier 2 — trusted-source web research.** Reuse KI-P2's existing `ResearchCoordinator`/
   `KnowledgeGapResearchRunner` machinery as-is — this ADR does not propose rebuilding it, only
   invoking it as the second tier when Tier 1 has no answer.
4. **Tier 3 — LLM general knowledge fallback.** The one tier that is **not** grounded — must
   be visibly and unambiguously labeled as such wherever it surfaces (CLAUDE.md §12.3:
   citations are mandatory for factual GRC output; a Tier 3 answer is the one case where "no
   citation" is the honest answer, and the UI/API contract must say so explicitly rather than
   presenting it alongside cited answers indistinguishably).
5. **Where this plugs in** needs its own investigation: the Knowledge Agent's own retrieval
   call, `apps/api`'s any future "ask a regulatory question" endpoint, and/or KI-P2's own gap
   research runner (should Tier 2 research even trigger if Tier 1 already has a confident
   answer, or does gap detection stay unaware of Tier 1 entirely?) all have different
   integration costs not yet sized.

## Explicitly out of scope for this ADR (and for KI-P7)

- No code changes. This is a tracking record only.
- No changes to `grc_rag`, `apps/api`'s retrieval/search routes, the Knowledge Agent, or
  `KnowledgeGapResearchRunner` — all confirmed untouched by KI-P7 (ADR-0031).
- No decision yet on confidence thresholds, caching, or how a Tier 1/Tier 2 disagreement
  (the internal DB and trusted-source research return conflicting answers) should be
  surfaced — real design questions for the implementation pass, not resolved here.

## Consequences of deferring

**Positive**
- KI-P7 (ADR-0031) ships a real, working, scoped approval-and-embeddings pipeline without
  entangling it with a second, larger, not-yet-designed retrieval change — smaller reviewable
  diffs, matching CLAUDE.md's "ship small, ship safe."
- The intent is written down now, while the context (why Tier 1 must be the *approved,
  official* text, not just any fetched text) is fresh, rather than relying on tribal memory
  once this session ends.

**Negative**
- Approved, embedded regulation sections (ADR-0031) sit unused by any retrieval path until
  this ADR is picked up and implemented — a real, acknowledged gap, not a hidden one.
- Two independently-evolving grounding pipelines (KI-P2's research, KI-P6/P7's regulations)
  continue to exist without a shared arbitration layer until this work happens; a caller
  wanting "the best available grounded answer" today must know to query both separately.

## Alternatives considered

- **Build a minimal version of the merge inside KI-P7 anyway**, reasoning that a small first
  cut would be low-risk. Rejected per explicit, repeated instruction this session: the task
  was scoped to catalog ingestion, storage, extraction, versioning, approval workflow, and
  embeddings only — "Do NOT modify the current RAG retrieval priority in this task" was
  stated as a hard boundary, not a suggestion.
- **Track this only as an informal TODO comment in code** rather than a numbered ADR.
  Rejected: CLAUDE.md §23 requires an ADR for any change touching retrieval/grounding
  architecture, and a Proposed ADR is more discoverable and harder to lose than a code
  comment — matching how ADL-0008 already tracks the (also-deferred) knowledge-persistence
  re-alignment decision.
