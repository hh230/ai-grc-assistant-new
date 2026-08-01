# knowledge-runtime (V2)

**Runtime, per-tenant ingestion of customer documents** — product roadmap **P1**, the change that
turns the capabilities from "answer over the shared global library" into "answer over **the
customer's own data**". It re-implements nothing: it **consumes** the frozen `knowledge-importer`
chunker and `retrieval-engine` corpus/providers.

```
customer document text
        │  ingest_document(kb, text, tenant=…, source_filename=…)
        ▼
knowledge-importer chunk_document ─→ Chunk[] ─→ tenant-scoped CorpusChunk[] ─→ TenantKnowledgeBase
                                                                                      │
                                     search-tools / RetrievalEngine ◄── keyword_provider()
```

## What it does

- **Chunks** a document with `knowledge-importer`'s `chunk_document` (fallback windowing handles any
  document shape — no profile needed).
- **Stamps tenant scope** on every chunk (`scope_kind=ORGANIZATION`, `organization_id=<tenant>`,
  ADR 0040) — so retrieval only ever returns a chunk within the tenant that uploaded it.
- **Guarantees citability** — the retrieval citation gate drops any chunk lacking a source file and a
  hard locator, so ingested chunks always get a source filename and, when the document has no
  page/code, a stable position locator (`§N`). Customer content is retrievable *and* honestly cited.
- **Is searchable now** via `keyword_provider()` (plug into `RetrievalEngine` or `search-tools`).

## Tenant isolation (fail-closed)

A search scoped to tenant A never returns tenant B's ingested data. If a query matches an
out-of-scope chunk, the engine's defence-in-depth (ADR 0040 §4) refuses to proceed and the search
returns `ok=False` — **it never leaks** (proven in the tests, including two tenants sharing one base).

## Production

The in-memory `TenantKnowledgeBase` is deliberately swappable: in production the same tenant-scoped
chunks are written to **pgvector** (`retrieval-engine`'s `PgVectorProvider`, same provider
interface), and nothing above this package changes.

## Usage

```python
from knowledge_runtime import TenantKnowledgeBase, ingest_document
from search_tools import build_local_search_tool

kb = TenantKnowledgeBase()
ingest_document(kb, doc_text, tenant=tenant, document_id="d1", source_filename="policy.pdf")
search = build_local_search_tool(kb.keyword_provider())   # now finds the customer's own content
```

## Tests

`uv run pytest` runs the full P1 loop with the **real** chunker and a **real** `search-tools` local
search: ingest → tenant-scoped citable chunks → retrievable for the owner → fail-closed for any other
tenant. No Postgres, no LLM. `ruff` + `mypy --strict` clean.
