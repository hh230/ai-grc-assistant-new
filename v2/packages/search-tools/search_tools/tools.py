"""The three concrete search tools, each a `SearchTool` over a `RetrievalEngine` built from the
providers the caller supplies. The tools differ only in which retrieval modality is active:

- `local_search`  — lexical / keyword only (no embeddings needed): real keyword provider, no vector.
- `vector_search` — semantic only: real vector provider, no keyword.
- `hybrid_search` — both, fused (the engine's full vector ∥ keyword → RRF path).

Disabling a modality is done with a null provider that returns no hits — so all three reuse the
frozen engine's fusion / ranking / citation / scope logic unchanged (nothing is re-implemented).
The `RetrievalEngine` and the concrete providers (`PgVectorProvider`, keyword providers, in-memory)
are the platform's; this module only wires them into a `Tool`.
"""

from __future__ import annotations

from pipeline_contracts import DEFAULT_TOP_K
from retrieval_engine import RetrievalEngine
from retrieval_engine.providers.interfaces import (
    Filter,
    KeywordSearchProvider,
    ScoredHit,
    VectorSearchProvider,
)

from search_tools.search import SearchTool

LOCAL_SEARCH_TOOL = "local_search"
VECTOR_SEARCH_TOOL = "vector_search"
HYBRID_SEARCH_TOOL = "hybrid_search"


class _NoVectorProvider:
    """A vector provider that contributes nothing — used to build a keyword-only search."""

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        return []


class _NoKeywordProvider:
    """A keyword provider that contributes nothing — used to build a vector-only search."""

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        return []


def build_local_search_tool(
    keyword_provider: KeywordSearchProvider, *, top_k: int = DEFAULT_TOP_K
) -> SearchTool:
    """Lexical search over the tenant's knowledge — no embeddings required."""
    return SearchTool(
        RetrievalEngine(_NoVectorProvider(), keyword_provider),
        name=LOCAL_SEARCH_TOOL,
        description="Lexical (keyword) search over the tenant's knowledge base; cited results.",
        top_k=top_k,
    )


def build_vector_search_tool(
    vector_provider: VectorSearchProvider, *, top_k: int = DEFAULT_TOP_K
) -> SearchTool:
    """Semantic (vector) search over the tenant's knowledge — wraps e.g. `PgVectorProvider`."""
    return SearchTool(
        RetrievalEngine(vector_provider, _NoKeywordProvider()),
        name=VECTOR_SEARCH_TOOL,
        description="Semantic (vector) search over the tenant's knowledge base; cited results.",
        top_k=top_k,
    )


def build_hybrid_search_tool(
    vector_provider: VectorSearchProvider,
    keyword_provider: KeywordSearchProvider,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> SearchTool:
    """Hybrid search: vector ∥ keyword fused (the engine's full retrieval path)."""
    return SearchTool(
        RetrievalEngine(vector_provider, keyword_provider),
        name=HYBRID_SEARCH_TOOL,
        description="Hybrid (vector + keyword) search over the tenant's knowledge base; cited.",
        top_k=top_k,
    )
