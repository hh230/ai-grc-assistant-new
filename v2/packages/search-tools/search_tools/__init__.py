"""Rasheed V2 Search Tools — real, read-only GRC search tools that **wrap the frozen
`retrieval-engine`** (vector ∥ keyword → RRF fusion → ranking → citation gate → tenant-scoped
`RetrievedContext`). Three registered tools — `local_search`, `vector_search`, `hybrid_search` —
that map the step instruction to a tenant-scoped `RetrievalQuery`, run the engine, and return the
cited results as a `ToolStepResult`. Pure adapters: no retrieval re-implementation, no LLM, no Core
change.
"""

from search_tools.search import SearchTool
from search_tools.tools import (
    HYBRID_SEARCH_TOOL,
    LOCAL_SEARCH_TOOL,
    VECTOR_SEARCH_TOOL,
    build_hybrid_search_tool,
    build_local_search_tool,
    build_vector_search_tool,
)

__all__ = [
    "SearchTool",
    "build_local_search_tool",
    "build_vector_search_tool",
    "build_hybrid_search_tool",
    "LOCAL_SEARCH_TOOL",
    "VECTOR_SEARCH_TOOL",
    "HYBRID_SEARCH_TOOL",
]
