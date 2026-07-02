"""Value objects for the Knowledge Extraction bounded context.

Immutable, self-validating. The output value objects (ExtractionCandidate,
CandidateRelationship) deliberately mirror the inputs of ``KnowledgeObject.extract`` and
``KnowledgeRelationship.declare`` so the integration layer can map them 1:1, with no
translation logic in between. They reuse the Knowledge Domain's value objects rather than
duplicating them.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..knowledge import (
    ContentHash,
    DocumentFormat,
    DocumentType,
    KnowledgeObjectPayload,
    KnowledgeObjectType,
    NormativeStrength,
    ProvenanceRecord,
    RelationshipEndpoint,
    RelationshipPredicate,
    StorageLocator,
)
from ..shared.value_objects import Confidence
from .enums import ExtractionStage


@dataclass(frozen=True)
class RawDocumentDescriptor:
    """The raw input to a run: a pointer to the bytes plus declared metadata. Never the bytes."""

    storage_locator: StorageLocator
    content_hash: ContentHash
    declared_format: DocumentFormat
    declared_document_type: DocumentType | None = None
    declared_language: str | None = None
    byte_size: int | None = None

    def __post_init__(self) -> None:
        if self.byte_size is not None and self.byte_size < 0:
            raise ValueError("RawDocumentDescriptor byte_size must be >= 0")


@dataclass(frozen=True)
class ExtractionError:
    """A structured failure within a stage. ``retryable`` distinguishes transient from fatal."""

    stage: ExtractionStage
    code: str
    message: str
    retryable: bool = False

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("ExtractionError code must not be empty")
        if not self.message.strip():
            raise ValueError("ExtractionError message must not be empty")


@dataclass(frozen=True)
class ExtractionCandidate:
    """A proposed knowledge object before it is persisted (and before ids are assigned).

    Maps 1:1 onto ``KnowledgeObject.extract``: the integration layer supplies the ids and
    canonical lineage (keyed by ``stable_key``) and creates the EXTRACTED object.
    """

    object_type: KnowledgeObjectType
    stable_key: str
    verbatim_text: str
    provenance: ProvenanceRecord
    normalized_statement: str | None = None
    normative_strength: NormativeStrength = NormativeStrength.INFORMATIVE
    language: str | None = None
    party_role: str | None = None
    confidence: Confidence | None = None
    payload: KnowledgeObjectPayload | None = None
    extractor_name: str | None = None
    extractor_version: str | None = None

    def __post_init__(self) -> None:
        if not self.stable_key.strip():
            raise ValueError("ExtractionCandidate stable_key must not be empty")
        if not self.verbatim_text.strip():
            raise ValueError("ExtractionCandidate verbatim_text must not be empty")
        if self.payload is not None:
            declared = getattr(type(self.payload), "OBJECT_TYPE", None)
            if declared is None:
                raise ValueError(
                    "ExtractionCandidate payload must declare OBJECT_TYPE (be a concrete payload)"
                )
            if declared != self.object_type:
                raise ValueError(
                    f"payload type {declared.value} does not match object_type "
                    f"{self.object_type.value}"
                )


@dataclass(frozen=True)
class CandidateRelationship:
    """A proposed graph edge before it is persisted. Maps 1:1 onto
    ``KnowledgeRelationship.declare``."""

    predicate: RelationshipPredicate
    subject: RelationshipEndpoint
    target: RelationshipEndpoint
    provenance: ProvenanceRecord
    confidence: Confidence | None = None
    extractor_name: str | None = None
    extractor_version: str | None = None

    def __post_init__(self) -> None:
        if self.subject == self.target:
            raise ValueError("CandidateRelationship cannot connect an endpoint to itself")
