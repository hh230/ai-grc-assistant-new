"""KnowledgeGraph — the **System of Record** (ADR 0058). **Append-only** (§10.11): nodes
and edges are added, never mutated or removed; a new edition appends new (version-pinned)
nodes and the old ones are retained. Ingesting an artifact is **idempotent** — keyed on the
artifact `content_hash`, re-ingesting the same artifact is a no-op.

This is *not* the serving layer. It holds the historical truth; the current queryable view
(Serving Index) is a separate, upsert layer built downstream.
"""
from __future__ import annotations

from dataclasses import dataclass

from knowledge_extraction.port import CanonicalExtractionArtifact, KnowledgeEntity


class GraphError(RuntimeError):
    """An operation would violate the append-only System-of-Record invariant."""


@dataclass(frozen=True, slots=True)
class GraphNode:
    entity_id: str          # version-pinned identity (§2.2) — the node key
    source_id: str
    version: str
    type: str               # canonical §3.5
    native_node_type: str
    name: str
    number: str | None
    parent: str | None
    authority: str
    license: str
    stability: str
    confidence: str
    description: str
    from_content_hash: str  # provenance: which artifact contributed this node

    @property
    def content_signature(self) -> tuple[object, ...]:
        """The knowledge content, excluding provenance — used for the append-only check."""
        return (
            self.entity_id, self.source_id, self.version, self.type, self.native_node_type,
            self.name, self.number, self.parent, self.authority, self.license,
            self.stability, self.confidence, self.description,
        )


@dataclass(frozen=True, slots=True)
class GraphEdge:
    type: str               # e.g. "contains" (structural); Tier-2 semantic edges later
    source: str             # parent entity_id
    target: str             # child entity_id
    from_content_hash: str


def _node_from(entity: KnowledgeEntity, content_hash: str) -> GraphNode:
    return GraphNode(
        entity_id=entity.entity_id, source_id=entity.source_id, version=entity.version,
        type=entity.type, native_node_type=entity.native_node_type, name=entity.name,
        number=entity.number, parent=entity.parent, authority=entity.authority,
        license=entity.license, stability=entity.stability, confidence=entity.confidence,
        description=entity.description, from_content_hash=content_hash,
    )


class KnowledgeGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[tuple[str, str, str], GraphEdge] = {}
        self._ingested: set[str] = set()  # artifact content_hashes

    # --- append-only, idempotent ingestion --------------------------------
    def append_artifact(self, artifact: CanonicalExtractionArtifact) -> "KnowledgeGraph":
        content_hash = artifact.identity.content_hash
        if content_hash in self._ingested:
            return self  # idempotent — same artifact already in the record

        staged: dict[str, GraphNode] = {}
        for entity in artifact.entities:
            node = _node_from(entity, content_hash)
            existing = self._nodes.get(node.entity_id)
            if existing is not None and existing.content_signature != node.content_signature:
                raise GraphError(
                    f"append-only violation: {node.entity_id} already in the record with "
                    f"different content (supersession must append a new version, not mutate)"
                )
            staged[node.entity_id] = node

        self._nodes.update(staged)
        for rel in artifact.structural_relationships:
            self._edges.setdefault(
                (rel.type, rel.source, rel.target),
                GraphEdge(rel.type, rel.source, rel.target, content_hash),
            )
        self._ingested.add(content_hash)
        return self

    # --- read-only queries -------------------------------------------------
    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    def sources(self) -> set[str]:
        return {n.source_id for n in self._nodes.values()}

    def ingested_artifacts(self) -> frozenset[str]:
        return frozenset(self._ingested)

    def counts_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for node in self._nodes.values():
            counts[node.type] = counts.get(node.type, 0) + 1
        return counts

    def node(self, entity_id: str) -> GraphNode | None:
        return self._nodes.get(entity_id)

    def all_nodes(self) -> tuple[GraphNode, ...]:
        return tuple(self._nodes.values())

    def all_edges(self) -> tuple[GraphEdge, ...]:
        return tuple(self._edges.values())

    def nodes_of(self, source_id: str) -> tuple[GraphNode, ...]:
        return tuple(n for n in self._nodes.values() if n.source_id == source_id)

    def children_of(self, entity_id: str) -> tuple[str, ...]:
        return tuple(e.target for e in self._edges.values()
                     if e.type == "contains" and e.source == entity_id)
