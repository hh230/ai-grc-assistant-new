"""An in-memory, tenant-scoped knowledge graph over the domain's knowledge model.

Nodes are ``KnowledgeObject``s; edges are ``KnowledgeRelationship``s (typed by
``RelationshipPredicate``, directed subject → target). The graph is the substrate Search (M9) and
Retrieval (M10) build on. It is **pure** (no I/O) and **tenant-isolated**: one graph holds a
single ``KnowledgeScope`` and refuses cross-scope content by construction (CLAUDE.md §20).

Edges may point at non-object endpoints (a document section or a framework control); those are
preserved but object-to-object edges are what traversal follows.
"""
from __future__ import annotations

from collections import deque
from enum import Enum

from grc_domain.knowledge import (
    KnowledgeObject,
    KnowledgeObjectType,
    KnowledgeRelationship,
    KnowledgeScope,
    RelationshipEndpoint,
    RelationshipEndpointKind,
    RelationshipPredicate,
)
from grc_domain.shared.identifiers import KnowledgeObjectId, KnowledgeRelationshipId

from .exceptions import CrossScopeError, NodeNotFoundError


class Direction(str, Enum):
    """Which way to follow edges, relative to a node."""

    OUTGOING = "outgoing"  # node is the subject
    INCOMING = "incoming"  # node is the target
    ANY = "any"


class KnowledgeGraph:
    """A single-tenant graph of knowledge objects and their typed relationships."""

    def __init__(self, scope: KnowledgeScope) -> None:
        self._scope = scope
        self._objects: dict[KnowledgeObjectId, KnowledgeObject] = {}
        self._relationships: dict[KnowledgeRelationshipId, KnowledgeRelationship] = {}
        self._outgoing: dict[KnowledgeObjectId, list[KnowledgeRelationshipId]] = {}
        self._incoming: dict[KnowledgeObjectId, list[KnowledgeRelationshipId]] = {}

    @property
    def scope(self) -> KnowledgeScope:
        return self._scope

    @property
    def object_count(self) -> int:
        return len(self._objects)

    @property
    def relationship_count(self) -> int:
        return len(self._relationships)

    # --- mutation ---------------------------------------------------------------------------
    def add_object(self, knowledge_object: KnowledgeObject) -> None:
        if knowledge_object.scope != self._scope:
            raise CrossScopeError(f"object {knowledge_object.id} is outside the graph's scope")
        self._objects[knowledge_object.id] = knowledge_object

    def add_relationship(self, relationship: KnowledgeRelationship) -> None:
        if relationship.scope != self._scope:
            raise CrossScopeError(f"relationship {relationship.id} is outside the graph's scope")
        self._relationships[relationship.id] = relationship
        subject_id = _object_id(relationship.subject)
        target_id = _object_id(relationship.target)
        if subject_id is not None:
            self._outgoing.setdefault(subject_id, []).append(relationship.id)
        if target_id is not None:
            self._incoming.setdefault(target_id, []).append(relationship.id)

    # --- lookup -----------------------------------------------------------------------------
    def has_object(self, object_id: KnowledgeObjectId) -> bool:
        return object_id in self._objects

    def get_object(self, object_id: KnowledgeObjectId) -> KnowledgeObject:
        knowledge_object = self._objects.get(object_id)
        if knowledge_object is None:
            raise NodeNotFoundError(str(object_id))
        return knowledge_object

    def objects_of_type(self, object_type: KnowledgeObjectType) -> tuple[KnowledgeObject, ...]:
        return tuple(o for o in self._objects.values() if o.object_type is object_type)

    def relationships_of(
        self,
        object_id: KnowledgeObjectId,
        *,
        direction: Direction = Direction.ANY,
        predicate: RelationshipPredicate | None = None,
    ) -> tuple[KnowledgeRelationship, ...]:
        relationship_ids: list[KnowledgeRelationshipId] = []
        if direction in (Direction.OUTGOING, Direction.ANY):
            relationship_ids.extend(self._outgoing.get(object_id, ()))
        if direction in (Direction.INCOMING, Direction.ANY):
            relationship_ids.extend(self._incoming.get(object_id, ()))
        relationships = [self._relationships[rid] for rid in dict.fromkeys(relationship_ids)]
        if predicate is not None:
            relationships = [r for r in relationships if r.predicate is predicate]
        return tuple(relationships)

    # --- traversal --------------------------------------------------------------------------
    def neighbors(
        self,
        object_id: KnowledgeObjectId,
        *,
        direction: Direction = Direction.OUTGOING,
        predicate: RelationshipPredicate | None = None,
    ) -> tuple[KnowledgeObjectId, ...]:
        """The object-node neighbors reachable from ``object_id`` over object-to-object edges."""
        result: list[KnowledgeObjectId] = []
        for relationship in self.relationships_of(
            object_id, direction=direction, predicate=predicate
        ):
            other = _other_object(relationship, object_id)
            if other is not None and other not in result:
                result.append(other)
        return tuple(result)

    def traverse(
        self,
        start: KnowledgeObjectId,
        *,
        max_depth: int = 3,
        direction: Direction = Direction.OUTGOING,
        predicate: RelationshipPredicate | None = None,
    ) -> tuple[KnowledgeObjectId, ...]:
        """Object ids reachable from ``start`` within ``max_depth`` (breadth-first)."""
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        visited: set[KnowledgeObjectId] = {start}
        ordered: list[KnowledgeObjectId] = []
        queue: deque[tuple[KnowledgeObjectId, int]] = deque([(start, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth == max_depth:
                continue
            for neighbor in self.neighbors(current, direction=direction, predicate=predicate):
                if neighbor not in visited:
                    visited.add(neighbor)
                    ordered.append(neighbor)
                    queue.append((neighbor, depth + 1))
        return tuple(ordered)

    def find_path(
        self,
        start: KnowledgeObjectId,
        end: KnowledgeObjectId,
        *,
        max_depth: int = 5,
        direction: Direction = Direction.OUTGOING,
    ) -> tuple[KnowledgeObjectId, ...] | None:
        """A shortest object path from ``start`` to ``end`` (inclusive), or ``None`` if none."""
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        queue: deque[tuple[KnowledgeObjectId, ...]] = deque([(start,)])
        visited: set[KnowledgeObjectId] = {start}
        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == end:
                return path
            if len(path) - 1 == max_depth:
                continue
            for neighbor in self.neighbors(current, direction=direction):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((*path, neighbor))
        return None


def _object_id(endpoint: RelationshipEndpoint) -> KnowledgeObjectId | None:
    if endpoint.kind is RelationshipEndpointKind.KNOWLEDGE_OBJECT:
        return endpoint.knowledge_object_id
    return None


def _other_object(
    relationship: KnowledgeRelationship, object_id: KnowledgeObjectId
) -> KnowledgeObjectId | None:
    subject_id = _object_id(relationship.subject)
    target_id = _object_id(relationship.target)
    if subject_id == object_id and target_id is not None and target_id != object_id:
        return target_id
    if target_id == object_id and subject_id is not None and subject_id != object_id:
        return subject_id
    return None
