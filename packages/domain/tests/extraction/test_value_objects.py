"""Unit tests for Knowledge Extraction value objects."""
from __future__ import annotations

import pytest
from grc_domain.extraction import (
    CandidateRelationship,
    ExtractionCandidate,
    ExtractionError,
    ExtractionStage,
    RawDocumentDescriptor,
)
from grc_domain.knowledge import (
    ContentHash,
    DefinitionPayload,
    DocumentFormat,
    KnowledgeObjectType,
    NormativeStrength,
    ProvenanceRecord,
    RelationshipEndpoint,
    RelationshipPredicate,
    StorageLocator,
)
from grc_domain.shared.identifiers import (
    KnowledgeObjectId,
    KnowledgeSourceVersionId,
)

VER = KnowledgeSourceVersionId("ver-1")
PROV = ProvenanceRecord(source_version_id=VER)


def make_descriptor(byte_size: int | None = 1024) -> RawDocumentDescriptor:
    return RawDocumentDescriptor(
        storage_locator=StorageLocator("s3://bucket/raw.pdf"),
        content_hash=ContentHash("sha256", "abc123"),
        declared_format=DocumentFormat.PDF,
        byte_size=byte_size,
    )


def test_raw_document_descriptor_rejects_negative_size() -> None:
    assert make_descriptor(0).byte_size == 0
    with pytest.raises(ValueError):
        make_descriptor(-1)


def test_extraction_error_requires_code_and_message() -> None:
    err = ExtractionError(stage=ExtractionStage.PARSE, code="parse_failed", message="boom")
    assert err.retryable is False
    with pytest.raises(ValueError):
        ExtractionError(stage=ExtractionStage.PARSE, code="  ", message="x")
    with pytest.raises(ValueError):
        ExtractionError(stage=ExtractionStage.PARSE, code="x", message="   ")


def test_extraction_candidate_valid() -> None:
    candidate = ExtractionCandidate(
        object_type=KnowledgeObjectType.REQUIREMENT,
        stable_key="ISO_27001:A.8.1",
        verbatim_text="The organization shall maintain an asset inventory.",
        provenance=PROV,
        normative_strength=NormativeStrength.MANDATORY,
    )
    assert candidate.stable_key == "ISO_27001:A.8.1"
    assert candidate.normative_strength is NormativeStrength.MANDATORY


def test_extraction_candidate_rejects_blank_fields() -> None:
    with pytest.raises(ValueError):
        ExtractionCandidate(
            object_type=KnowledgeObjectType.REQUIREMENT,
            stable_key="   ",
            verbatim_text="x",
            provenance=PROV,
        )
    with pytest.raises(ValueError):
        ExtractionCandidate(
            object_type=KnowledgeObjectType.REQUIREMENT,
            stable_key="k",
            verbatim_text="  ",
            provenance=PROV,
        )


def test_extraction_candidate_rejects_payload_type_mismatch() -> None:
    with pytest.raises(ValueError):
        ExtractionCandidate(
            object_type=KnowledgeObjectType.REQUIREMENT,
            stable_key="k",
            verbatim_text="x",
            provenance=PROV,
            payload=DefinitionPayload(term="Asset"),  # wrong payload for a requirement
        )


def test_candidate_relationship_rejects_self_reference() -> None:
    endpoint = RelationshipEndpoint.for_object(KnowledgeObjectId("obj-1"))
    with pytest.raises(ValueError):
        CandidateRelationship(
            predicate=RelationshipPredicate.SATISFIED_BY,
            subject=endpoint,
            target=endpoint,
            provenance=PROV,
        )


def test_candidate_relationship_valid() -> None:
    rel = CandidateRelationship(
        predicate=RelationshipPredicate.SATISFIED_BY,
        subject=RelationshipEndpoint.for_object(KnowledgeObjectId("req-1")),
        target=RelationshipEndpoint.for_object(KnowledgeObjectId("ctl-1")),
        provenance=PROV,
    )
    assert rel.predicate is RelationshipPredicate.SATISFIED_BY
