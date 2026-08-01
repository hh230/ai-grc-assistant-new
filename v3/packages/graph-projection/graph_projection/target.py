"""ProjectionTarget — the boundary (ADR 0059) with many realizations; and
MemoryProjectionTarget — the **reference realization** that proves the boundary is correct
(as the fake extractor proved the Extraction Port), needing no real store.

A target **reads** the immutable ProjectionPackage and applies each operation to its store,
translating the target-agnostic operations into the store's own commands. `SupabaseProjection`
(SQL), `Neo4jProjection` (Cypher), etc. come later — each behind this same boundary.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from graph_builder import GraphEdge, GraphNode
from graph_projection.package import ProjectionPackage


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    upserted_nodes: int
    upserted_edges: int
    deactivated_nodes: int
    deleted_edges: int


class ProjectionTarget(ABC):
    @abstractmethod
    def apply(self, package: ProjectionPackage) -> ProjectionResult:
        """Apply an immutable package to the store. Reads the package; never mutates it."""
        ...


class MemoryProjectionTarget(ProjectionTarget):
    """An in-memory serving view: upsert-based and **idempotent** — applying the same package
    twice leaves the same state. The `Requirement → knowledge_nodes/…` mapping a real store
    would make lives in *its* realization, never here and never in the projector."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}

    def apply(self, package: ProjectionPackage) -> ProjectionResult:
        node_index = package.node_index()
        edge_index = package.edge_index()
        upserted_nodes = upserted_edges = deactivated_nodes = deleted_edges = 0
        for operation in package.operations:
            if operation.kind == "upsert_node":
                self._nodes[operation.ref] = node_index[operation.ref]
                upserted_nodes += 1
            elif operation.kind == "upsert_edge":
                self._edges[operation.ref] = edge_index[operation.ref]
                upserted_edges += 1
            elif operation.kind == "deactivate_node":
                self._nodes.pop(operation.ref, None)
                deactivated_nodes += 1
            elif operation.kind == "delete_edge":
                self._edges.pop(operation.ref, None)
                deleted_edges += 1
        return ProjectionResult(
            upserted_nodes, upserted_edges, deactivated_nodes, deleted_edges
        )

    # --- serving-view queries ---------------------------------------------
    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    def node(self, entity_id: str) -> GraphNode | None:
        return self._nodes.get(entity_id)
