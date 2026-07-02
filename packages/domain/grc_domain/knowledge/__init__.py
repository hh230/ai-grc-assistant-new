"""Knowledge bounded context — the canonical, structured-knowledge domain model.

This is the heart of the platform: sources and their immutable, effective-dated versions;
the documents and sections that manifest a version; the extracted, version-pinned
KnowledgeObjects and their lineage (CanonicalKnowledgeObject); and the typed relationships
(graph edges) between them. Provenance is intrinsic to every fact and edge.

Pure domain: no persistence, infrastructure, RAG, embeddings, retrieval, or AI. (Repository
implementations and the extraction engine live in outer layers.)
"""
from __future__ import annotations

from .entities import (
    CanonicalKnowledgeObject,
    KnowledgeDocument,
    KnowledgeObject,
    KnowledgeRelationship,
    KnowledgeSection,
    KnowledgeSource,
    KnowledgeSourceVersion,
)
from .enums import (
    CurationStatus,
    DerivationMethod,
    DocumentFormat,
    DocumentType,
    KnowledgeDomain,
    KnowledgeObjectType,
    KnowledgeScopeKind,
    NormativeStrength,
    RelationshipEndpointKind,
    RelationshipPredicate,
    SectionType,
    VersionStatus,
)
from .exceptions import (
    IllegalKnowledgeObjectTransition,
    IllegalRelationshipTransition,
    IllegalVersionTransition,
    KnowledgeDocumentNotFound,
    KnowledgeSectionNotFound,
    PublishRequiresApproval,
    SelfReferentialRelationship,
    VersionImmutable,
    VersionRequiresDocument,
)
from .repositories import KnowledgeSourceRepository
from .value_objects import (
    Approval,
    ContentHash,
    ControlPayload,
    DefinitionPayload,
    KnowledgeObjectPayload,
    KnowledgeScope,
    LocalizedText,
    ObligationPayload,
    PageRange,
    ProvenanceRecord,
    RelationshipEndpoint,
    RequirementPayload,
    StorageLocator,
    StructuralAnchor,
    TextSpan,
)

__all__ = [
    # entities / aggregates
    "KnowledgeSource",
    "KnowledgeSourceVersion",
    "KnowledgeDocument",
    "KnowledgeSection",
    "CanonicalKnowledgeObject",
    "KnowledgeObject",
    "KnowledgeRelationship",
    # value objects
    "KnowledgeScope",
    "LocalizedText",
    "StructuralAnchor",
    "PageRange",
    "TextSpan",
    "ContentHash",
    "StorageLocator",
    "Approval",
    "ProvenanceRecord",
    "RelationshipEndpoint",
    "KnowledgeObjectPayload",
    "DefinitionPayload",
    "RequirementPayload",
    "ControlPayload",
    "ObligationPayload",
    # enums
    "KnowledgeScopeKind",
    "KnowledgeDomain",
    "DocumentType",
    "DocumentFormat",
    "SectionType",
    "VersionStatus",
    "KnowledgeObjectType",
    "NormativeStrength",
    "CurationStatus",
    "RelationshipPredicate",
    "RelationshipEndpointKind",
    "DerivationMethod",
    # exceptions
    "IllegalVersionTransition",
    "IllegalKnowledgeObjectTransition",
    "IllegalRelationshipTransition",
    "PublishRequiresApproval",
    "VersionRequiresDocument",
    "VersionImmutable",
    "SelfReferentialRelationship",
    "KnowledgeDocumentNotFound",
    "KnowledgeSectionNotFound",
    # repository interface (unchanged; implementations live in the persistence layer)
    "KnowledgeSourceRepository",
]
