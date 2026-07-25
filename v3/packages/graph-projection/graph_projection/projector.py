"""GraphProjector — Stage 2 (ADR 0059). Target-agnostic: it **transforms** a Knowledge
Graph + a ProjectionRequest into an immutable, execution-ready ProjectionPackage. It knows
**nothing** about Supabase / PostgreSQL / SQL / Neo4j / RDF.
"""
from __future__ import annotations

from graph_builder import GraphEdge, GraphNode, KnowledgeGraph
from graph_projection.package import ProjectionOperation, ProjectionPackage
from graph_projection.request import (
    ProjectDelta,
    ProjectionRequest,
    ProjectSnapshot,
    ProjectSource,
)


class GraphProjector:
    def project(
        self, graph: KnowledgeGraph, request: ProjectionRequest
    ) -> ProjectionPackage:
        nodes, edges, label = self._select(graph, request)
        operations = tuple(
            ProjectionOperation("upsert_node", n.entity_id) for n in nodes
        ) + tuple(
            ProjectionOperation("upsert_edge", f"{e.type}|{e.source}|{e.target}") for e in edges
        )
        return ProjectionPackage(
            request_label=label, nodes=nodes, relationships=edges, operations=operations
        )

    @staticmethod
    def _select(
        graph: KnowledgeGraph, request: ProjectionRequest
    ) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...], str]:
        if isinstance(request, ProjectSnapshot):
            return graph.all_nodes(), graph.all_edges(), "ProjectSnapshot"
        if isinstance(request, ProjectSource):
            nodes = tuple(
                n for n in graph.all_nodes()
                if n.source_id == request.source_id and n.version == request.version
            )
            ids = {n.entity_id for n in nodes}
            edges = tuple(e for e in graph.all_edges() if e.source in ids and e.target in ids)
            return nodes, edges, f"ProjectSource({request.source_id}@{request.version})"
        if isinstance(request, ProjectDelta):
            nodes = tuple(n for n in graph.all_nodes() if n.from_content_hash == request.content_hash)
            edges = tuple(e for e in graph.all_edges() if e.from_content_hash == request.content_hash)
            return nodes, edges, f"ProjectDelta({request.content_hash[:12]})"
        raise TypeError(f"unknown ProjectionRequest: {request!r}")  # pragma: no cover
