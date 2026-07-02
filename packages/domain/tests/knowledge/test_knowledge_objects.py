"""Unit tests for CanonicalKnowledgeObject and KnowledgeObject."""
from __future__ import annotations

import pytest

from grc_domain.knowledge import (
    CanonicalKnowledgeObject,
    ControlPayload,
    CurationStatus,
    DefinitionPayload,
    KnowledgeObject,
    KnowledgeObjectType,
    KnowledgeScope,
    NormativeStrength,
    ProvenanceRecord,
)
from grc_domain.knowledge.events import (
    CanonicalKnowledgeObjectStarted,
    KnowledgeObjectExtracted,
    KnowledgeObjectPublished,
)
from grc_domain.knowledge.exceptions import IllegalKnowledgeObjectTransition
from grc_domain.shared.exceptions import InvariantViolation
from grc_domain.shared.identifiers import (
    CanonicalKnowledgeObjectId,
    KnowledgeObjectId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
)

SRC = KnowledgeSourceId("src-1")
VER = KnowledgeSourceVersionId("ver-1")
CKO = CanonicalKnowledgeObjectId("cko-1")
OBJ = KnowledgeObjectId("obj-1")
SCOPE = KnowledgeScope.global_()
PROV = ProvenanceRecord(source_version_id=VER)


def make_object(
    *,
    object_type: KnowledgeObjectType = KnowledgeObjectType.REQUIREMENT,
    payload=None,
) -> KnowledgeObject:
    return KnowledgeObject.extract(
        id=OBJ,
        canonical_id=CKO,
        scope=SCOPE,
        object_type=object_type,
        source_version_id=VER,
        verbatim_text="The organization shall maintain an asset inventory.",
        provenance=PROV,
        normative_strength=NormativeStrength.MANDATORY,
        payload=payload,
    )


# --- CanonicalKnowledgeObject --------------------------------------------------------------
def test_start_canonical_object() -> None:
    cko = CanonicalKnowledgeObject.start(
        id=CKO,
        scope=SCOPE,
        object_type=KnowledgeObjectType.REQUIREMENT,
        source_id=SRC,
        stable_key="ISO_27001:A.8.1",
    )
    assert cko.stable_key == "ISO_27001:A.8.1"
    assert any(isinstance(e, CanonicalKnowledgeObjectStarted) for e in cko.pending_events)


def test_start_requires_stable_key() -> None:
    with pytest.raises(ValueError):
        CanonicalKnowledgeObject.start(
            id=CKO,
            scope=SCOPE,
            object_type=KnowledgeObjectType.REQUIREMENT,
            source_id=SRC,
            stable_key="  ",
        )


def test_register_revision_tracks_lineage_and_current() -> None:
    cko = CanonicalKnowledgeObject.start(
        id=CKO, scope=SCOPE, object_type=KnowledgeObjectType.REQUIREMENT,
        source_id=SRC, stable_key="ISO_27001:A.8.1",
    )
    rev_2013 = KnowledgeObjectId("obj-2013")
    rev_2022 = KnowledgeObjectId("obj-2022")
    cko.register_revision(rev_2013)
    cko.register_revision(rev_2022)
    assert cko.revision_ids == [rev_2013, rev_2022]
    assert cko.current_revision_id == rev_2022
    # idempotent re-register does not duplicate
    cko.register_revision(rev_2022)
    assert cko.revision_ids == [rev_2013, rev_2022]


def test_set_current_revision_must_be_registered() -> None:
    cko = CanonicalKnowledgeObject.start(
        id=CKO, scope=SCOPE, object_type=KnowledgeObjectType.REQUIREMENT,
        source_id=SRC, stable_key="k",
    )
    with pytest.raises(InvariantViolation):
        cko.set_current_revision(KnowledgeObjectId("never-registered"))


# --- KnowledgeObject -----------------------------------------------------------------------
def test_extract_records_event_and_defaults() -> None:
    obj = make_object()
    assert obj.status is CurationStatus.EXTRACTED
    assert obj.normative_strength is NormativeStrength.MANDATORY
    assert any(isinstance(e, KnowledgeObjectExtracted) for e in obj.pending_events)


def test_extract_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        KnowledgeObject.extract(
            id=OBJ, canonical_id=CKO, scope=SCOPE,
            object_type=KnowledgeObjectType.REQUIREMENT, source_version_id=VER,
            verbatim_text="   ", provenance=PROV,
        )


def test_extract_rejects_provenance_version_mismatch() -> None:
    wrong = ProvenanceRecord(source_version_id=KnowledgeSourceVersionId("other-version"))
    with pytest.raises(InvariantViolation):
        KnowledgeObject.extract(
            id=OBJ, canonical_id=CKO, scope=SCOPE,
            object_type=KnowledgeObjectType.REQUIREMENT, source_version_id=VER,
            verbatim_text="x", provenance=wrong,
        )


def test_extract_rejects_payload_type_mismatch() -> None:
    with pytest.raises(InvariantViolation):
        make_object(
            object_type=KnowledgeObjectType.REQUIREMENT,
            payload=DefinitionPayload(term="Asset"),  # wrong payload for a requirement
        )


def test_extract_accepts_matching_payload() -> None:
    obj = make_object(
        object_type=KnowledgeObjectType.CONTROL,
        payload=ControlPayload(code="A.8.1", control_family="Asset Management"),
    )
    assert isinstance(obj.payload, ControlPayload)


def test_curation_lifecycle_review_then_publish() -> None:
    obj = make_object()
    obj.submit_for_review()
    assert obj.status is CurationStatus.IN_REVIEW
    obj.publish()
    assert obj.is_published
    assert any(isinstance(e, KnowledgeObjectPublished) for e in obj.pending_events)


def test_cannot_publish_without_review_gate() -> None:
    obj = make_object()
    with pytest.raises(IllegalKnowledgeObjectTransition):
        obj.publish()  # EXTRACTED -> PUBLISHED is not allowed; must pass review


def test_supersede_published_object() -> None:
    obj = make_object()
    obj.submit_for_review()
    obj.publish()
    successor = KnowledgeObjectId("obj-2")
    obj.supersede(superseded_by_object_id=successor)
    assert obj.status is CurationStatus.SUPERSEDED
    assert obj.superseded_by_object_id == successor


def test_reject_requires_reason() -> None:
    obj = make_object()
    with pytest.raises(ValueError):
        obj.reject(reason="  ")
