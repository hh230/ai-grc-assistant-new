# ADR 0008: Knowledge & RAG architecture

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §12; ADR 0007, 0012, 0015

## Context

In GRC, an uncited or hallucinated claim is unacceptable — outputs must be grounded in the
customer's own evidence and in framework libraries, with citations, confidence, and
reproducibility. Retrieval must be strictly tenant-isolated and must support compliance
documents in many formats and languages.

## Decision

We adopt a first-class **RAG** subsystem exposed to agents as Tools, with two pipelines:

- **Ingestion:** tenant-tagged source intake → parsing/normalization (PDF/DOCX/XLSX, with
  structure preserved) → semantic/section-aware chunking with metadata → provider-abstracted
  embedding → idempotent indexing in pgvector/Postgres for hybrid retrieval.
- **Retrieval:** tenant-scoped query construction → hybrid search (vector + keyword +
  metadata, `tenant_id` filtered first) → re-ranking → bounded context assembly →
  grounded, structured generation including citations and a confidence signal → schema
  validation that rejects uncited factual claims and escalates on low confidence.

Rules: tenant isolation is absolute; citations are mandatory; confidence is surfaced (low
confidence triggers a human gate); retrieved source IDs and model/prompt versions are
logged for reproducibility; embedders, vector stores, chunking, and re-rankers sit behind
swappable interfaces.

## Consequences

**Positive**
- Trustworthy, auditable, reproducible answers grounded in customer evidence.
- "Insufficient evidence" instead of guessing on thin or low-confidence results.
- Component swappability (embeddings/vector store/re-ranker) without touching business code.

**Negative / costs**
- Retrieval quality (chunking, hybrid weighting, re-ranking) needs ongoing tuning and eval.
- Ingestion of diverse formats/languages is non-trivial and must be robust.

## Alternatives considered

- **Pure LLM generation (no retrieval).** Rejected: hallucination risk is unacceptable in
  GRC.
- **Fine-tuning instead of retrieval.** Rejected: customer-specific, frequently-changing
  evidence is unsuited to fine-tuning; retrieval gives provenance and freshness.
