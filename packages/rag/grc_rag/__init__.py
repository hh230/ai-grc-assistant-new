"""grc_rag — Retrieval-Augmented Generation: search and retrieval over knowledge.

Milestone 9 (Search) provides lexical, tenant-scoped keyword search over knowledge objects — the
keyword half of the hybrid retrieval in CLAUDE.md §12. Retrieval (M10) and grounded generation
(M11) build on it; the semantic/vector half and the LLM generator plug in behind interfaces once
an embedding/LLM provider is selected.
"""
from __future__ import annotations

from .exceptions import CrossScopeError, RagError
from .generation import Citation, GroundedAnswer, parse_and_validate
from .pipeline import RagPipeline
from .retrieval import KnowledgeRetriever, RetrievalContext, RetrievedChunk
from .search import LexicalSearchIndex, SearchResult
from .semantic import SemanticHit, SemanticSearchIndex

__all__ = [
    # search (M9)
    "LexicalSearchIndex",
    "SearchResult",
    # retrieval (M10)
    "KnowledgeRetriever",
    "RetrievalContext",
    "RetrievedChunk",
    "SemanticSearchIndex",
    "SemanticHit",
    # RAG (M11)
    "RagPipeline",
    "GroundedAnswer",
    "Citation",
    "parse_and_validate",
    # errors
    "RagError",
    "CrossScopeError",
]
