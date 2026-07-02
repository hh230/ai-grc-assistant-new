"""Errors raised by the Knowledge Graph."""
from __future__ import annotations


class KnowledgeGraphError(Exception):
    """Base class for knowledge-graph errors."""


class NodeNotFoundError(KnowledgeGraphError):
    """Raised when a requested knowledge-object node is not in the graph."""


class CrossScopeError(KnowledgeGraphError):
    """Raised when adding an object/relationship whose tenant scope differs from the graph's.

    Tenant isolation is absolute (CLAUDE.md §20): a graph holds a single scope and refuses
    cross-tenant content by construction.
    """
