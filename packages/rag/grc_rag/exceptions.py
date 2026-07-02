"""Errors raised by the RAG package (search, retrieval)."""
from __future__ import annotations


class RagError(Exception):
    """Base class for RAG-layer errors."""


class CrossScopeError(RagError):
    """Raised when indexing content whose tenant scope differs from the index's.

    Tenant isolation is absolute (CLAUDE.md §20): an index holds one scope by construction.
    """
