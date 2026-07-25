# graph-projection — the Projection boundary (ADR 0059)

The boundary between the append-only **Knowledge Graph** (System of Record) and any serving store.
Built in the owner's order, boundary-first and reference-realization-first:

```
ProjectionRequest              ← what to project (ProjectSource · ProjectDelta · ProjectSnapshot)
      │
      ▼
GraphProjector                 ← target-agnostic transform: Graph + Request → Package (knows no store)
      │
      ▼
ProjectionPackage (immutable)  ← nodes · relationships · operations (upsert/deactivate/delete) — NO SQL
      │
      ├── MemoryProjectionTarget   ← reference realization (proves the boundary; in-memory, idempotent)
      ├── SupabaseProjection       ← later: INSERT/UPDATE/DELETE
      ├── Neo4jProjection          ← later: Cypher
      └── …
```

## The six principles (all enforced/proven)

1. **Request-scoped** — the projector is asked *what* (a source, a delta, a snapshot); it never loads
   the whole graph unless asked. `ProjectSource("ISO-27001","2022")` → 97 nodes / 93 edges, not 387.
2. **Target-agnostic** — `GraphProjector` / `ProjectionPackage` import **no** store (a test scans for
   `supabase`/`psycopg`/`sqlalchemy`/`neo4j`/`rdflib`/…). No SQL, Cypher, or triples in the core.
3. **`ProjectionPackage` is immutable** — a frozen dataclass of tuples; a target only *reads* it.
4. **One boundary, many realizations** — `ProjectionTarget.apply(package)`; the store-specific mapping
   (`Requirement` → `knowledge_nodes`/`controls`/`documents`) lives in the realization.
5. **Reference realization first** — `MemoryProjectionTarget` proves the Port before any real store,
   exactly as the fake extractor proved the Extraction Port.
6. **Serving Layer ⇒ Upsert · Idempotent · Incremental** — re-applying the same package is a no-op.

## Run

```bash
cd v3/packages/graph-projection && \
  PYTHONPATH="../graph-builder:../knowledge-extraction:../artifact-writers" python -m pytest -q
```
