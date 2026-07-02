"""Unit tests for KnowledgeRelationship (graph edges)."""
from __future__ import annotations

import pytest

from grc_domain.knowledge import (
    CurationStatus,
    KnowledgeRelationship,
    KnowledgeScope,
    ProvenanceRecord,
    RelationshipEndpoint,
    RelationshipPredicate,
    SelfReferentialRelationship,
)
from grc_domain.knowledge.events import (
    KnowledgeRelationshipAsserted,
    KnowledgeRelationshipPublished,
)
from grc_domain.knowledge.exceptions import IllegalRelationshipTransition
from grc_domain.shared.identifiers import (
    FrameworkControlId,
    FrameworkId,
    KnowledgeObjectId,
    KnowledgeRelationshipId,
    KnowledgeSourceVersionId,
)

REL = KnowledgeRelationshipId("rel-1")
SCOPE = KnowledgeScope.global_()
PROV = ProvenanceRecord(source_version_id=KnowledgeSourceVersionId("ver-1"))

REQUIREMENT = RelationshipEndpoint.for_object(KnowledgeObjectId("req-1"))
CONTROL = RelationshipEndpoint.for_object(KnowledgeObjectId("ctl-1"))
FRAMEWORK_CONTROL = RelationshipEndpoint.for_framework_control(
    FrameworkId("framework:iso_27001"), FrameworkControlId("A.8.1")
)


def make_relationship(
    *,
    predicate: RelationshipPredicate = RelationshipPredicate.SATISFIED_BY,
    subject: RelationshipEndpoint = REQUIREMENT,
    target: RelationshipEndpoint = CONTROL,
) -> KnowledgeRelationship:
    return KnowledgeRelationship.declare(
        id=REL, scope=SCOPE, predicate=predicate, subject=subject, target=target,
        provenance=PROV,
    )


def test_declare_edge_records_event() -> None:
    rel = make_relationship()
    assert rel.predicate is RelationshipPredicate.SATISFIED_BY
    assert rel.status is CurationStatus.EXTRACTED
    assert any(isinstance(e, KnowledgeRelationshipAsserted) for e in rel.pending_events)


def test_declare_rejects_self_reference() -> None:
    with pytest.raises(SelfReferentialRelationship):
        make_relationship(subject=REQUIREMENT, target=REQUIREMENT)


def test_edge_can_target_external_framework_control() -> None:
    rel = make_relationship(
        predicate=RelationshipPredicate.MAPPED_TO,
        subject=CONTROL,
        target=FRAMEWORK_CONTROL,
    )
    assert rel.target.framework_control_id == FrameworkControlId("A.8.1")


def test_relationship_lifecycle_review_then_publish() -> None:
    rel = make_relationship()
    rel.submit_for_review()
    assert rel.status is CurationStatus.IN_REVIEW
    rel.publish()
    assert rel.is_published
    assert any(isinstance(e, KnowledgeRelationshipPublished) for e in rel.pending_events)


def test_relationship_cannot_publish_without_review() -> None:
    rel = make_relationship()
    with pytest.raises(IllegalRelationshipTransition):
        rel.publish()


def test_relationship_supersede() -> None:
    rel = make_relationship()
    rel.submit_for_review()
    rel.publish()
    successor = KnowledgeRelationshipId("rel-2")
    rel.supersede(superseded_by_relationship_id=successor)
    assert rel.status is CurationStatus.SUPERSEDED
    assert rel.superseded_by_relationship_id == successor
