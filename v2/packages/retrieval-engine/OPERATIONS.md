# pgvector adapter — operations (Phase 9B)

Operational documentation for the PostgreSQL + pgvector vector backend that replaces the
temporary `InMemoryVectorProvider`. All numbers below are measured against the real corpus
(**117 documents / 31,793 chunks**, 1536-dim embeddings) on the local dev pgvector server.

The Retrieval Engine (`engine.py`, `planner.py`, `fusion.py`, `ranking.py`, `citation.py`)
was **not modified** for this phase — `PgVectorProvider` is a drop-in behind the existing
`VectorSearchProvider` port.

---

## 1. PostgreSQL schema

Isolated database (`rasheed_v2` by default — **never** V1's `aigrc`). One table:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_vectors (
    chunk_id           text PRIMARY KEY,
    document_id        text NOT NULL,
    embedding          vector(1536) NOT NULL,
    embedding_model    text NOT NULL,
    embedding_version  text NOT NULL,
    chunk_checksum     text NOT NULL,
    -- metadata for the Filter predicate only:
    document_profile   text,
    structure_profile  text,
    category           text,
    language           text,
    code               text,
    content_type       text,
    updated_at         timestamptz NOT NULL DEFAULT now()
);
```

**No unnecessary duplication.** The table stores the vector, the provenance keys
(`embedding_model` / `embedding_version` / `chunk_checksum`, which drive incremental
import), and only the columns the `Filter` predicate needs. It deliberately does **not**
store the chunk text, title, heading path, or page numbers — those live in the generated
chunk artifacts and are joined into the result payload by `chunk_id`. The table is the
vector *index*, not a copy of the corpus.

Canonical DDL: `migrations/0001_knowledge_vectors.sql` (or `pg/schema.py`).

---

## 2. pgvector configuration

- **Distance:** cosine (`vector_cosine_ops`, the `<=>` operator). Embeddings are
  L2-normalized at generation time, so cosine similarity = `1 - (embedding <=> query)`.
- **Dimension:** 1536 — the exact value the Knowledge Library chose so vectors fit under
  pgvector's **2000-dim HNSW index cap**.
- **`hnsw.ef_search = 100`** (per session) — the query-time recall/latency knob.
- **`enable_seqscan = off`** on the provider's dedicated ANN connection. On a table this
  small the planner's cost model otherwise prefers a sequential scan (computing all 31,793
  distances), which measured **~40× slower** than the HNSW index scan (185 ms → 4.5 ms).
  The provider connection only ever issues `ORDER BY embedding <=> q LIMIT k`, so forcing
  the index there is safe and standard; it affects no other connection and not V1.

---

## 3. Index strategy — HNSW vs IVFFlat

**Chosen: HNSW.** Evaluated both:

| | HNSW (chosen) | IVFFlat |
|---|---|---|
| Recall / latency | Higher recall, lower query latency | Lower recall unless well-tuned |
| Build | Slower build, no training step | Faster build, but needs `lists` tuning + data present to train |
| Incremental inserts | Maintained incrementally on INSERT/UPDATE | Degrades as data drifts from trained centroids; needs periodic rebuild |
| Fit for this corpus | Ideal at ~32k–low-millions vectors | Better only at very large scale with careful tuning |

At 31,793 vectors, HNSW is the clear choice: best recall/latency, no `lists`/centroid
tuning, and — critically for our **incremental import** — it maintains itself on
insert/update, so re-imports don't require an index rebuild. Parameters:
`m = 16, ef_construction = 64` (pgvector defaults, good for this scale).

Measured (real corpus): HNSW query **p50 4.5 ms** (index scan) vs **185 ms** (seq scan).

---

## 4. Import pipeline

`python -m retrieval_engine.pg.import_vectors` — **idempotent, resumable, incremental.**

Strategy: bulk-`COPY` every embedding into a `TEMP` staging table → diff staging against the
live table to count insert/update/skip → a single `ON CONFLICT` merge that updates **only**
rows whose `chunk_checksum` / `embedding_model` / `embedding_version` changed, and prunes
rows no longer present. The whole merge is one transaction.

- **Idempotent:** re-running with unchanged embeddings writes nothing (all skipped).
- **Incremental:** only changed embeddings are updated (verified: staleing one row → next
  import reports `updated = 1`, the rest skipped).
- **Resumable:** an interruption mid-merge rolls back cleanly; re-running completes (skips
  unchanged). The HNSW index is built after the initial bulk load (fast); later imports
  leave the existing index to maintain itself.

**Measured (initial load of 31,793):**

| Stage | Duration |
|---|---|
| Bulk COPY + merge | ~20 s |
| HNSW index build | ~114 s |
| **Total** | **~134 s** |

Re-run (no changes): `inserted 0, updated 0, skipped 31793, pruned 0`, no reindex.

---

## 5. Observability

`import_vectors` reports (`ImportStats.to_dict()`): `total_in_files`, `inserted`,
`updated`, `skipped`, `pruned`, `load_seconds`, `index_seconds`, `index_built`, and a
`db_stats` block (`row_count`, `total_size`, `table_size`, per-index sizes). `pg/schema.py::stats()`
returns the same DB statistics on demand.

**Measured storage:**

| Object | Size |
|---|---|
| Rows | 31,793 |
| Table | 11 MB |
| HNSW index | 232 MB |
| Filter indexes (6) | ~1.7 MB total |
| **Total relation** | **500 MB** |

Query duration is measured by the benchmark (`pg/benchmark.py`) and carried on every
`RetrievedContext.timings_ms` (`vector_ms`, `keyword_ms`, `total_ms`).

---

## 6. Benchmark — InMemory vs PgVector (real corpus)

| Metric | InMemoryVectorProvider | PgVectorProvider |
|---|---|---|
| Index/setup | matrix build ~7 s | import 20 s + HNSW 114 s (one-time) |
| Vector query p50 | 5.9 ms | 11.9 ms |
| Vector query p95 | 7.6 ms | 24.9 ms |
| Vector throughput | ~166 qps | ~71 qps |
| **Process RAM (vectors)** | **+339 MB held in-process** | **0 — vectors live in PostgreSQL** |

The operational win: PgVector keeps **zero vectors in process memory** and scales past what
fits in RAM, at single-digit-to-low-tens-of-ms query latency. InMemory is marginally faster
per query but holds the entire 339 MB matrix in every process.

---

## 7. Validation — results match or improve

100 representative queries (English + Arabic) through the **unchanged** engine, InMemory vs
PgVector:

- **top-1 citation identical: 98/100 (98%)**
- mean top-5 overlap: **0.968**
- mean |confidence Δ|: **0.0001**
- engine latency: InMemory p50 12 ms / PgVector p50 22 ms

The 2 differing top-1s were the same query, and come **only** from HNSW's approximate ANN
acting on the low-weight, **non-semantic** Phase-4 hash vectors (fusion weights keyword 1.0,
vector 0.4). With real semantic embeddings the vector signal becomes meaningful and HNSW
recall is tuned via `ef_search`; the engine and this adapter do not change.

---

## 8. Operational considerations

- **Isolation:** default DSN targets `rasheed_v2`; V1's `aigrc` is never touched. Override
  with `RETRIEVAL_PG_DSN`.
- **Filtered ANN:** the `Filter` compiles to a SQL `WHERE` applied with the ANN. With very
  selective filters, raise `hnsw.ef_search` (or rely on pgvector 0.8 iterative scans) to
  keep enough post-filter candidates.
- **Re-embedding:** when embeddings are regenerated (new model/version), bump the
  embedding version; the next import updates the changed rows and HNSW maintains itself.
- **Backups / DR:** standard PostgreSQL — the vector table is ordinary data plus one HNSW
  index; `pg_dump`/PITR apply.
- **Scaling:** at low-millions of vectors, keep HNSW; revisit `m`/`ef_construction` and
  connection pooling. Beyond that, partition by tenant/scope or shard.
- **Connection lifecycle:** `PgVectorProvider` holds one autocommit connection (call
  `.close()`); in a service, front it with a pool.
```
