# search-tools (V2)

Real, read-only GRC search tools that **wrap the frozen `retrieval-engine`** — they re-implement
nothing. The engine's full path (vector ∥ keyword → RRF fusion → ranking → citation gate →
tenant-scoped `RetrievedContext`) runs unchanged; these tools just map a mission step to a query and
the result to a `ToolStepResult`.

| tool name | modality | wraps |
|---|---|---|
| `local_search` | lexical / keyword (no embeddings) | `RetrievalEngine` + keyword provider |
| `vector_search` | semantic | `RetrievalEngine` + vector provider (e.g. `PgVectorProvider`) |
| `hybrid_search` | both, fused | `RetrievalEngine` + both providers |

One `SearchTool` class backs all three; a modality is disabled with a null provider, so every tool
reuses the engine's fusion/ranking/citation/scope logic. A plan step routes to one by name via
`PlanStep.tool` (ADR 0048):

    Mission → ExecutionPort → RegistryExecutor → local_search → RetrievalEngine → cited results

## Contract

- **Input:** the step `instruction` is the search query.
- **Tenant isolation (CLAUDE.md §20, ADR 0040):** the query's `Filter.scope` is
  `RetrievalScope.for_tenant(tenant.tenant_id)` — the engine returns this tenant's data ∪ shared
  global knowledge, **never another tenant's**. If a provider ever admitted an out-of-scope chunk,
  the engine's defence-in-depth refuses to proceed and the tool returns `ok=False` (fail-closed) —
  it never leaks. (Production's `PgVectorProvider` scopes in SQL, so that path is graceful.)
- **Output:** a `ToolStepResult` (ADR 0049) — `output` lists the cited results, `source_ids` carries
  the matched chunk ids as provenance, `confidence` is the engine's overall confidence, `warnings`
  carries the engine's (e.g. "insufficient evidence").
- **Failure is safe:** an empty query or a tenancy refusal returns `ok=False`.

## Usage

```python
from search_tools import build_vector_search_tool, build_local_search_tool
from tool_registry import ToolRegistry

registry = ToolRegistry()
registry.register(build_local_search_tool(keyword_provider))     # providers from retrieval-engine
registry.register(build_vector_search_tool(pgvector_provider))   # e.g. PgVectorProvider

# a step then names it: PlanStep(instruction="access control", tool="local_search")
```

## Tests

`uv run pytest` runs the tools against the **real** engine with retrieval-engine's in-memory
providers over a small GRC corpus: lexical match + citations + provenance, semantic ranking,
fail-closed tenant isolation, and a mission **E2E** through the real `RegistryExecutor`. No network,
no LLM. `ruff` + `mypy --strict` clean (retrieval-engine consumed as an untyped import).
