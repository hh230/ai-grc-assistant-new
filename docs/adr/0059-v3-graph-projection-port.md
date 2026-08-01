# ADR 0059: The Graph Projection boundary — one Port, many target realizations

- Status: **Accepted** (2026-07-25) — owner-accepted **with two refinements** (see Decision): the input
  is a **`ProjectionRequest`** (not the whole graph), and the target-agnostic output is a
  **`ProjectionPackage`** of operations (not counts, not SQL rows). **Boundary-first; we do not start
  Supabase directly.** Likely the last big boundary in V3 — after it, adding a store is a *realization*,
  not an architecture change.
- Date: 2026-07-25
- Deciders: **Product Owner**, Architecture
- Related: ADR 0058 (Pipeline Execution Model — the Projection sits between the Knowledge Graph and the
  Serving layer; *System of Record = Append-only, Serving = Upsert*) · ADR 0056 (the same one-Port /
  many-realizations pattern that worked for extraction) · CANONICAL-MODEL §10.11 (append-only) ·
  CLAUDE.md §17 (plugins via registries).

## Context

The **Knowledge Graph** is the truth (System of Record, append-only). But a serving store keeps it in
**its own shape**: a `Requirement` node might become `knowledge_nodes`, or `controls`, or `documents`
rows; edges might become a join table, Cypher relationships, or RDF triples. That **mapping must not
live in the Graph Builder** — putting it there couples all of V3 to one store (Supabase) and repeats
the mistake the Extraction Port was created to avoid. We need a boundary so the serving store is
**replaceable**.

## Decision

**We will split projection into a target-agnostic *plan* and a target-specific *apply*, joined by a
`ProjectionPackage`. The store is chosen by realizing the *apply* boundary — never by loading the
whole graph, and never by emitting SQL from the core.**

- **Input is a `ProjectionRequest`, not the whole graph.** The stage is asked *what* to project and
  resolves it against the Knowledge Graph itself — so the Port never has to load the entire graph on
  every call:
  - `ProjectSource(source_id, version)` — one source.
  - `ProjectDelta(since_content_hash)` — everything appended since a point (a daily delta).
  - `ProjectSnapshot()` — the full current view (e.g. building a fresh environment).
- **A target-agnostic `GraphProjector` produces a `ProjectionPackage`.** `project(graph, request) →
  ProjectionPackage`. *(It **transforms**; it does not merely "plan" — the package is execution-ready.)*
  The package is the intermediate contract — **not counts, not SQL rows**:
  - `nodes`, `relationships`, and **`operations`** — a list of **target-agnostic** operations:
    `UpsertNode · UpsertEdge · DeactivateNode · DeleteEdge` (equivalently `Create · Update ·
    Deactivate`). **No SQL, no Cypher, no triples.**
- **The `ProjectionPackage` is immutable — like the Artifact.** Once built, **no Target may modify
  it**; a Target only *reads* it, and if it needs something extra it makes its **own copy** and never
  touches the package. The whole pipeline becomes a chain of immutable hand-offs:
  `Artifact → Knowledge Graph → Projection Package → Projection Target → Serving`.
- **The `ProjectionTarget` boundary has many realizations.** `apply(package) → ProjectionResult`.
  `SupabaseProjection` translates the operations to `INSERT/UPDATE/DELETE`; `Neo4jProjection` to
  Cypher; `RdfProjection` to triples. The **store-specific mapping lives entirely here** — that a
  `Requirement` becomes `knowledge_nodes` / `controls` / `documents` is Supabase's private decision.
- **Serving Layer ⇒ Upsert · Idempotent · Incremental** (ADR 0058): re-applying the same package is a
  no-op; a `ProjectDelta` / `ProjectSource` upserts only that scope; the graph stays the append-only
  truth.

```
ProjectionRequest + Knowledge Graph
        │
        ▼
   GraphProjector      (target-agnostic)
        │
        ▼
   ProjectionPackage   (immutable · nodes · relationships · operations — no SQL)
        │
        ├── SupabaseProjection  → INSERT / UPDATE / DELETE
        ├── Neo4jProjection     → Cypher
        ├── RdfProjection       → triples
        └── …
```

**Build order (owner) — boundary-first, reference-realization-first:** (1) `ProjectionRequest`
(`ProjectSource` · `ProjectDelta` · `ProjectSnapshot`); (2) `GraphProjector` (Graph → Package, knows no
store); (3) `ProjectionTarget` (interface only); (4) **`MemoryProjectionTarget`** — the *reference
realization* that proves the boundary is correct, exactly as the fake extractor proved the Extraction
Port; (5) only then `SupabaseProjection` (when a Supabase environment exists).

## Consequences

**Positive**
- The serving store is replaceable: swapping Supabase → Neo4j is a new realization, no change to the
  Graph Builder, the Knowledge Graph, or any extractor.
- The Graph Builder stays pure (no store knowledge); the mapping is isolated and independently
  testable per target.
- Idempotent + incremental projection falls out of ADR 0058, so upserts are safe to retry.
- **Request-scoped, not graph-scoped:** projecting one source, a daily delta, or a fresh snapshot are
  all the same boundary — no full-graph load per call. The `ProjectionPackage` (operations, no SQL) is
  a **portable plan** any target can apply — or diff/audit *before* writing.
- Plausibly the **last large boundary** in V3; everything after is realizations.

**Negative / costs**
- One more seam (Port + realization) instead of writing Supabase calls directly — a deliberate,
  low-cost indirection, the same trade the Extraction Port made.
- Each target realization must define and maintain its own mapping and idempotency keys.

## Alternatives considered

- **Project directly inside the Graph Builder (Supabase calls in Stage 4).** Rejected — couples V3 to
  one store; the exact coupling this ADR removes.
- **A Supabase-specific port / no boundary.** Rejected — the Wave-1 / extraction lesson: start from the
  boundary, not from an implementation.
