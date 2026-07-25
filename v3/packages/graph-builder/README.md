# graph-builder — Stage 4: the append-only Knowledge Graph

The first **downstream pipeline stage** (ADR 0058). It turns Canonical Extraction Artifacts into a
**Knowledge Graph** — the **System of Record**, which is **Append-only** (§10.11).

- **`KnowledgeGraph`** — nodes (entities, keyed by version-pinned `entity_id`) + edges (the
  `contains` structural relationships the extractor emitted). Append-only: a new edition **appends**
  new version-pinned nodes; the old ones are **retained, never edited**. Semantic (Tier-2) edges are
  added by a later stage; this one carries structure only.
- **`GraphBuilder`** — Stage 4. Conforms to ADR 0058:
  - **Independent** — runs on *any* artifact; it imports **no extractor**. It reads the archive via
    `artifact-writers`' `JsonArtifactReader`.
  - **Idempotent** — re-ingesting the same artifact (`content_hash`) is a **no-op**.
  - **Incremental** — folds one source's artifact into an existing graph, **no rebuild**.
  - **Append-only** — a conflicting redefinition of an `entity_id` raises `GraphError`; nodes are
    never silently mutated.

## Proven on the three real sources

```
nodes: 387 · edges: 334 · sources: {NIST-CSF, ISO-27001, KSA-PDPL-LAW}
counts_by_type: Function 6 · Category 26 · Subcategory 106 · Control 93 · Requirement 137 · Definition 19
re-append same 3 → 387 nodes (unchanged)   # idempotent
```

## Run

```bash
cd v3/packages/graph-builder && PYTHONPATH="../knowledge-extraction:../artifact-writers" python -m pytest -q
```

**System of Record = Append-only. Serving Layers = Incremental Upsert.** This package is the former;
the Supabase serving layer, Embeddings, and AI Index (upsert) are the next stages.
