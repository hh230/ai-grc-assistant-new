# retrieval-engine (V2)

The Retrieval Engine core (Phase 9A), built on **ports and adapters**. It retrieves a
ranked, **cited** context bundle from the generated knowledge artifacts — metadata
filtering → vector + keyword (BM25) search → reciprocal-rank fusion → deterministic ranking
→ citation validation → context assembly → `RetrievedContext`.

Implements [v2/docs/architecture/retrieval-engine.md](../../docs/architecture/retrieval-engine.md).
**No generation, no LLM, no RAG.** The engine depends only on the provider *ports*, so the
vector backend is a wiring choice: `InMemoryVectorProvider` (dev/tests) or, as of Phase 9B,
the production `PgVectorProvider` (PostgreSQL + pgvector) — the engine, planner, fusion,
ranking, citation, and assembly are byte-identical either way.

V2-only, isolated: standalone `uv` project, its own `.venv`/`uv.lock`. Targets an isolated
`rasheed_v2` database; never touches V1 (`aigrc`).

## Installation & optional extras

The core package installs with **pipeline-contracts only** — no `numpy`, `psycopg`, or
`pgvector` — and imports cleanly without them. The heavier backends are optional extras,
imported lazily so a base install stays light:

- **base** — the engine, planner, fusion, ranking, citation, assembly, and the
  `InMemoryKeywordProvider` (BM25). No database, no numpy.
- **`retrieval-engine[vectors]`** — adds `numpy` for `InMemoryVectorProvider` (in-memory
  cosine over the embedding artifacts). No database.
- **`retrieval-engine[pgvector]`** — adds `psycopg` + `pgvector` (+ `numpy`) for the
  production `PgVectorProvider`. The SDKs are imported lazily inside the provider, so nothing
  above needs PostgreSQL to import.

(Running the test suite via `uv sync` installs all of these through the dev dependency group.)

## Usage

```python
from pathlib import Path
from retrieval_engine import RetrievalEngine, RetrievalQuery, Filter
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider

corpus = InMemoryCorpus.load(Path("v2/knowledge/chunks"))
keyword = InMemoryKeywordProvider(corpus)
vector = InMemoryVectorProvider.load(corpus, Path("v2/knowledge/embeddings"))

engine = RetrievalEngine(vector, keyword)
ctx = engine.retrieve(RetrievalQuery(text="access control policy", top_k=3,
                                     filter=Filter(document_profiles=("iso_standard",))))
for r in ctx.results:
    print(r.citation.formatted, r.confidence)
```

## Run tests and the real-corpus demo

```bash
cd v2/packages/retrieval-engine
uv sync
uv run pytest                        # 23 unit tests (synthetic corpus, no artifacts needed)
uv run python -m retrieval_engine.demo   # 50 GRC queries against the real 117-doc corpus
```

## Architecture (ports & adapters)

```
retrieval_engine/
  engine.py        RetrievalEngine.retrieve() — orchestration + context assembly → RetrievedContext
  planner.py       RetrievalQuery → RetrievalPlan (filter, over-fetch depth, weights)
  fusion.py        reciprocal rank fusion (scale-free, weighted)
  ranking.py       deterministic GRC boosts (exact-code, language, heading-only)
  citation.py      re-export shim → pipeline_contracts.citations (the GRC gate + formatting
                   are defined there, once, for the whole platform)
  text.py          Arabic/English normalization + tokenization
  providers/
    interfaces.py       ports (VectorSearchProvider, KeywordSearchProvider) + value objects
                        (Filter, CorpusChunk, ScoredHit, FusedHit, Citation, RetrievedChunk, RetrievedContext)
    corpus.py           InMemoryCorpus loader + passes_filter (metadata predicate)
    vector.py           hash query embedder (matches Phase 4)
    keyword.py          BM25 scoring (idf + fielded term score)
    inmemory_vector.py  InMemoryVectorProvider — numpy cosine over the embedding artifacts
    inmemory_keyword.py InMemoryKeywordProvider — BM25 over the chunk text
```

The engine imports only `interfaces` — never a concrete provider. `RetrievalEngine(vector,
keyword)` accepts anything implementing the two `Protocol`s (proven by a test that runs the
engine with a fake vector provider). This is exactly what makes the pgvector swap a wiring
change.

## What it does

- **Metadata filtering** (`Filter`) applied *inside* each provider before scoring: by
  document profile, category, structure profile, language, document id, or clause-code
  prefix. Tenant scope slots in here later.
- **Vector search** — filtered cosine over the embedding artifacts (numpy).
- **Keyword search** — filtered BM25 over chunk text, with a field boost for terms matching
  a chunk's code / title / heading path; bilingual (Arabic-normalized) tokenization.
- **Reciprocal rank fusion** — fuses the two on rank (scale-free), weighted per plan.
- **Ranking** — small, transparent, logged GRC boosts after fusion.
- **Citation validation** — a chunk only surfaces if it resolves to a live citation
  (source + clause code or page); non-citable chunks are dropped. Every result carries a
  structured + formatted citation.
- **Context assembly** — the top-k validated chunks with scores, confidence, and citations,
  as a `RetrievedContext`.

## Honest caveats (for this phase)

- The corpus vectors are the Phase-4 **local hash embeddings — not semantically meaningful**
  (see `providers/vector.py`), so vector search contributes little real relevance today.
  **Keyword/BM25 carries relevance** — which the 50-query demo shows working well. The
  default fusion weights favour keyword accordingly. Real semantic embeddings (OpenAI, …)
  and a cross-encoder reranker (a later phase) sharpen this; the engine and ports do not
  change.
- A handful of Arabic source PDFs have parse-time glyph corruption (documented in earlier
  phases); citations still resolve to source + page, but their text can be garbled.
- No cross-encoder reranker in this phase (it's in the retrieval architecture, a later
  slice).

## pgvector backend (Phase 9B)

`PgVectorProvider` is the production drop-in for `InMemoryVectorProvider` — same
`VectorSearchProvider` port, so the engine runs unchanged and never learns that vectors live
in PostgreSQL. Vectors + filter metadata sit in a `knowledge_vectors` table; the ANN runs
through an HNSW index (cosine). Chunk payloads are resolved from the corpus by `chunk_id`,
so the table never duplicates the corpus text.

```python
from retrieval_engine.providers.pgvector_provider import PgVectorProvider
vector = PgVectorProvider(corpus)                 # reads RETRIEVAL_PG_DSN (default rasheed_v2)
engine = RetrievalEngine(vector, keyword)         # identical engine, identical results
```

```bash
# schema + idempotent, incremental import of every embedding into PostgreSQL
python -m retrieval_engine.pg.import_vectors
# InMemory vs PgVector benchmark + 100-query validation
python -m retrieval_engine.pg.benchmark
```

Schema DDL: `migrations/0001_knowledge_vectors.sql`. Full schema, index-strategy rationale
(HNSW vs IVFFlat), import pipeline, benchmark/validation numbers, and operational notes:
[OPERATIONS.md](OPERATIONS.md).

## Not in this phase

No generation, no LLM, no RAG, no cross-encoder reranker. Phase 9B swapped only the vector
storage backend; the engine, planner, fusion, ranking, citation, and assembly are untouched.
