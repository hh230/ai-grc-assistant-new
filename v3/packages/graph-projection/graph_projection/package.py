"""ProjectionPackage — the **immutable**, target-agnostic contract between the projector
and any target (ADR 0059). Once built, no Target may modify it — a Target only reads it (if
it needs more, it makes its own copy). Carries the node/edge payloads and a list of
execution-ready **operations** — no SQL, no Cypher, no triples.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from graph_builder import GraphEdge, GraphNode

OperationKind = Literal["upsert_node", "upsert_edge", "deactivate_node", "delete_edge"]


def edge_key(edge: GraphEdge) -> str:
    """A stable string key for an edge (used to reference it in operations)."""
    return f"{edge.type}|{edge.source}|{edge.target}"


@dataclass(frozen=True, slots=True)
class ProjectionOperation:
    kind: OperationKind
    ref: str   # node op → `entity_id`; edge op → `edge_key(...)`


@dataclass(frozen=True, slots=True)
class ProjectionPackage:
    """Immutable (frozen + tuples). A target reads `operations` and applies each, looking up
    payloads in `nodes` / `relationships`."""

    request_label: str
    nodes: tuple[GraphNode, ...]
    relationships: tuple[GraphEdge, ...]
    operations: tuple[ProjectionOperation, ...]

    def node_index(self) -> dict[str, GraphNode]:
        return {n.entity_id: n for n in self.nodes}

    def edge_index(self) -> dict[str, GraphEdge]:
        return {edge_key(e): e for e in self.relationships}
