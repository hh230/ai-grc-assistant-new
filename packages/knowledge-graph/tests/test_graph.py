"""Unit tests for the in-memory KnowledgeGraph: nodes, edges, queries, traversal, isolation."""
from __future__ import annotations

import pytest
from grc_domain.knowledge import (
    KnowledgeObject,
    KnowledgeObjectType,
    KnowledgeRelationship,
    KnowledgeScope,
    ProvenanceRecord,
    RelationshipEndpoint,
    RelationshipPredicate,
)
from grc_domain.shared.identifiers import (
    CanonicalKnowledgeObjectId,
    FrameworkControlId,
    FrameworkId,
    KnowledgeObjectId,
    KnowledgeRelationshipId,
    KnowledgeSourceVersionId,
    OrganizationId,
)
from grc_knowledge_graph import (
    CrossScopeError,
    Direction,
    KnowledgeGraph,
    NodeNotFoundError,
)

SCOPE = KnowledgeScope.global_()
ORG_SCOPE = KnowledgeScope.for_organization(OrganizationId("org-1"))
VER = KnowledgeSourceVersionId("ver-1")
PROV = ProvenanceRecord(source_version_id=VER)


def obj(
    object_key: str,
    object_type: KnowledgeObjectType = KnowledgeObjectType.REQUIREMENT,
    *,
    scope: KnowledgeScope = SCOPE,
) -> KnowledgeObject:
    return KnowledgeObject.extract(
        id=KnowledgeObjectId(object_key),
        canonical_id=CanonicalKnowledgeObjectId(f"c-{object_key}"),
        scope=scope,
        object_type=object_type,
        source_version_id=VER,
        verbatim_text=f"Statement {object_key}",
        provenance=PROV,
    )


def edge(
    relationship_key: str,
    subject_key: str,
    target: RelationshipEndpoint,
    predicate: RelationshipPredicate = RelationshipPredicate.SATISFIED_BY,
) -> KnowledgeRelationship:
    return KnowledgeRelationship.declare(
        id=KnowledgeRelationshipId(relationship_key),
        scope=SCOPE,
        predicate=predicate,
        subject=RelationshipEndpoint.for_object(KnowledgeObjectId(subject_key)),
        target=target,
        provenance=PROV,
    )


def to_object(object_key: str) -> RelationshipEndpoint:
    return RelationshipEndpoint.for_object(KnowledgeObjectId(object_key))


def sample_graph() -> KnowledgeGraph:
    """req-1 -SATISFIED_BY-> ctl-1 -IMPLEMENTS-> ev-1; ctl-1 -MAPPED_TO-> a framework control."""
    graph = KnowledgeGraph(SCOPE)
    graph.add_object(obj("req-1", KnowledgeObjectType.REQUIREMENT))
    graph.add_object(obj("ctl-1", KnowledgeObjectType.CONTROL))
    graph.add_object(obj("ev-1", KnowledgeObjectType.EVIDENCE_EXPECTATION))
    graph.add_object(obj("risk-1", KnowledgeObjectType.RISK))
    graph.add_relationship(
        edge("r1", "req-1", to_object("ctl-1"), RelationshipPredicate.SATISFIED_BY)
    )
    graph.add_relationship(edge("r2", "ctl-1", to_object("ev-1"), RelationshipPredicate.IMPLEMENTS))
    graph.add_relationship(
        edge(
            "r3",
            "ctl-1",
            RelationshipEndpoint.for_framework_control(
                FrameworkId("framework:iso_27001"), FrameworkControlId("A.8.1")
            ),
            RelationshipPredicate.MAPPED_TO,
        )
    )
    return graph


# --- nodes & lookup ------------------------------------------------------------------------
def test_counts() -> None:
    graph = sample_graph()
    assert graph.object_count == 4
    assert graph.relationship_count == 3


def test_get_and_has_object() -> None:
    graph = sample_graph()
    assert graph.has_object(KnowledgeObjectId("ctl-1")) is True
    assert graph.get_object(KnowledgeObjectId("ctl-1")).object_type is KnowledgeObjectType.CONTROL
    with pytest.raises(NodeNotFoundError):
        graph.get_object(KnowledgeObjectId("absent"))


def test_objects_of_type() -> None:
    controls = sample_graph().objects_of_type(KnowledgeObjectType.CONTROL)
    assert tuple(c.id for c in controls) == (KnowledgeObjectId("ctl-1"),)


# --- edges & neighbors ---------------------------------------------------------------------
def test_outgoing_neighbors_follow_object_edges_only() -> None:
    graph = sample_graph()
    assert graph.neighbors(KnowledgeObjectId("req-1")) == (KnowledgeObjectId("ctl-1"),)
    # ctl-1's framework-control edge is not an object neighbor
    assert graph.neighbors(KnowledgeObjectId("ctl-1")) == (KnowledgeObjectId("ev-1"),)


def test_incoming_neighbors() -> None:
    graph = sample_graph()
    assert graph.neighbors(KnowledgeObjectId("ctl-1"), direction=Direction.INCOMING) == (
        KnowledgeObjectId("req-1"),
    )


def test_neighbors_filtered_by_predicate() -> None:
    graph = sample_graph()
    assert graph.neighbors(
        KnowledgeObjectId("ctl-1"), predicate=RelationshipPredicate.IMPLEMENTS
    ) == (KnowledgeObjectId("ev-1"),)
    assert (
        graph.neighbors(KnowledgeObjectId("ctl-1"), predicate=RelationshipPredicate.SATISFIED_BY)
        == ()
    )


def test_relationships_of_by_direction() -> None:
    graph = sample_graph()
    assert (
        len(graph.relationships_of(KnowledgeObjectId("ctl-1"), direction=Direction.OUTGOING)) == 2
    )
    assert len(graph.relationships_of(KnowledgeObjectId("ctl-1"), direction=Direction.ANY)) == 3


# --- traversal -----------------------------------------------------------------------------
def test_traverse_breadth_first() -> None:
    graph = sample_graph()
    assert graph.traverse(KnowledgeObjectId("req-1"), max_depth=2) == (
        KnowledgeObjectId("ctl-1"),
        KnowledgeObjectId("ev-1"),
    )
    assert graph.traverse(KnowledgeObjectId("req-1"), max_depth=1) == (KnowledgeObjectId("ctl-1"),)


def test_find_path() -> None:
    graph = sample_graph()
    assert graph.find_path(KnowledgeObjectId("req-1"), KnowledgeObjectId("ev-1")) == (
        KnowledgeObjectId("req-1"),
        KnowledgeObjectId("ctl-1"),
        KnowledgeObjectId("ev-1"),
    )
    assert graph.find_path(KnowledgeObjectId("req-1"), KnowledgeObjectId("risk-1")) is None


def test_traverse_rejects_negative_depth() -> None:
    with pytest.raises(ValueError, match="max_depth"):
        sample_graph().traverse(KnowledgeObjectId("req-1"), max_depth=-1)


# --- tenant isolation ----------------------------------------------------------------------
def test_cross_scope_object_is_rejected() -> None:
    graph = KnowledgeGraph(SCOPE)
    with pytest.raises(CrossScopeError):
        graph.add_object(obj("x", scope=ORG_SCOPE))
