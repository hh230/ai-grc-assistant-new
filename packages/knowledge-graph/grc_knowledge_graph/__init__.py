"""grc_knowledge_graph — an in-memory, tenant-scoped knowledge graph (Handbook §8 milestone 8).

A pure graph over the domain's ``KnowledgeObject`` nodes and ``KnowledgeRelationship`` edges,
with typed neighbor/traversal/path queries. Single-tenant by construction (tenant isolation is
absolute). Depends only on ``grc_domain``; it is the substrate Search and Retrieval build on.
"""
from __future__ import annotations

from .exceptions import CrossScopeError, KnowledgeGraphError, NodeNotFoundError
from .graph import Direction, KnowledgeGraph

__all__ = [
    "KnowledgeGraph",
    "Direction",
    "KnowledgeGraphError",
    "NodeNotFoundError",
    "CrossScopeError",
]
