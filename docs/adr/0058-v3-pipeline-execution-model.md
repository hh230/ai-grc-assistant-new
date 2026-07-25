# ADR 0058: The V3 downstream pipeline execution model — Fail-Open, Incremental, Independent & Idempotent

- Status: **Accepted** (2026-07-25) — owner-accepted **with the System-of-Record vs Serving-Layers
  distinction** (Decision rule 4). Formalizes the owner's five rules for how the pipeline *runs*.
  Governs every downstream stage (Graph Builder → Supabase Serving Layer → Embeddings → AI). No stage
  is built against a different execution model.
- Date: 2026-07-25
- Deciders: **Product Owner**, Architecture
- Related: [technical-debt.md](../../v3/docs/reports/technical-debt.md) (fail-open protocol + debt
  register) · ADR 0056 (Extraction Port) · ADR 0057 (Artifact; `Structure ≠ Semantics`) ·
  CANONICAL-MODEL §0.1 (stage roadmap), §4 (Tier-1/Tier-2), §10.11 (append-only) · CLAUDE.md §12
  (idempotency & retries) · §16 (EDA — idempotent, at-least-once).

## Context

Extraction yields Canonical Extraction Artifacts, but only some sources are extractable now (3 built;
~110 pending extractors; 5 debt items). The downstream stages (Graph Builder, Supabase, Embeddings, AI)
must not wait for all 117 sources, and must not be frozen by one bad source. The **Reference
Guarantees** prove *design* quality — they must not become a **Production Gate**. We need an execution
model that yields a working system from day one while keeping quality honest.

## Decision

**The V3 downstream pipeline obeys five rules. Every stage is built against them.**

1. **Fail-Open production.** No production stage stops because of **one source or one extractor**. On
   extraction failure the source becomes a recorded **Technical Debt** entry (honest, never silently
   dropped, never heuristically "fixed") and the pipeline **continues**:
   `Source → Extractor → (Success → Artifact) / (Failure → Technical Debt → continue)`.
2. **Reference Guarantees ≠ Production Gate.** Guarantees prove design quality. A guarantee left
   unproven **because of a rendition** (not an architecture flaw) is carried as debt, not a freeze.
   *(`no new Extractor may break a **proven** guarantee` still holds.)*
3. **Incremental from day one.** The pipeline runs on whatever artifacts exist: `first Artifact → Graph
   Builder`; `each subsequent Artifact → Upsert`. Results appear before all sources exist — the system
   is not a batch that waits for 113 completions before the first result.
4. **Incremental, no full rebuild — and the layers are distinct.** A newly-resolved or newly-built
   source flows `Extract → Graph append → Serving upsert → Embed (that source only)`. The Knowledge
   Base is **never** rebuilt end-to-end for one source.

   > **System of Record = Append-only. Serving Layers = Incremental Upsert.**

   This preserves the V3 principle *Knowledge is Append-only* (§10.11) and prevents any future
   confusion between **storing** knowledge and **serving** it:

   ```
   Artifact Archive  (Append-only)          ← System of Record: knowledge, never modified — only added
     → Knowledge Graph (Append-only)        ← System of Record: a new edition APPENDS a version
       → Projection    (Graph Projection Port, ADR 0059)  ← maps the SoR onto a target's shape
         → Serving      (Upsert)            ← Serving Layer: current queryable view, not historical truth
           → Embeddings → AI
   ```
   The **Projection Layer** (ADR 0059) sits between the Knowledge Graph and any serving store: the SoR
   is the truth, but a target (Supabase / Neo4j / RDF / …) stores it in its own shape (e.g. a
   `Requirement` node → `knowledge_nodes` / `controls` / `documents` rows). That mapping lives in a
   **projection realization**, never in the Graph Builder — which keeps the serving store replaceable.
   - **Artifact + Knowledge Graph = the System of Record — append-only.** ISO-27001 changing in 2027
     **appends** `@2027` entities and edges; the `@2022` graph is **retained, never edited**.
   - **Serving Index / Embeddings / AI Index (and Supabase *when it is the serving layer*) = Serving
     Layers — Incremental Upsert.** They reflect the *current* view and do **not** represent historical
     truth. *(If a Supabase table instead holds the append-only record, it is a System-of-Record table,
     not a serving one. Which physical store plays which role is a persistence-stage decision,
     §0.1 Stage 6.)*
5. **Every stage is Independent & Idempotent.** Graph Builder, Supabase Sync, Embeddings, and AI Index
   each **run standalone**; re-running a stage on the same input is a **no-op** — the append-only
   System-of-Record skips an already-ingested `content_hash`, the serving layers upsert to the same
   value; **no stage depends on re-running everything before it.**

**Build ordering (owner, refined 2026-07-25):** (1) keep the extractors as-is (NIST/ISO/PDPL);
(2) **Graph Builder** → **Knowledge Graph (append-only)**; (3) **Graph Projection Port** (ADR 0059) +
its first realization (**Supabase Projection**, upsert) — *not Supabase directly*; (4) Embeddings
(incremental); (5) wire the AI; then (6) build the remaining ~110 extractors **in parallel**. *Prove
the pipeline end-to-end on the 3 existing artifacts, then scale.*

## Consequences

**Positive**
- A working system from day one (first result on the first artifact), not after 117 completions.
- One bad source (e.g. `NCA-ECC` identity-degraded rendition) never freezes the platform.
- Each stage is testable and runnable alone; a new/clean source is **appended** to the System of
  Record and **upserted** into the serving layers — no rebuild, and history is never rewritten.
- Extractor development (~110) parallelizes against a stable, running pipeline.

**Negative / costs**
- Every stage must carry idempotency keys and upsert semantics (more design per stage than a batch run).
- The debt register must be kept honest and visible so "fail-open" never becomes "quietly incomplete".

## Alternatives considered

- **Batch: finish all 113 extractors → then Graph → Supabase.** Rejected — no result until everything
  is done, and one bad source blocks all.
- **Reference Guarantees as a hard Production Gate.** Rejected — freezes the project on an isolated
  rendition issue; conflates design proof with production readiness.
- **Full rebuild on each new source.** Rejected — violates incremental/idempotent; does not scale.
