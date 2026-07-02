"""Domain events for the Knowledge bounded context.

Immutable, past-tense facts recorded by aggregate roots when meaningful state changes. The
domain never publishes them; infrastructure later pulls and relays them. Creation events
carry tenant scope so downstream consumers can attribute them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..shared.events import DomainEvent
from ..shared.identifiers import (
    CanonicalKnowledgeObjectId,
    KnowledgeDocumentId,
    KnowledgeObjectId,
    KnowledgeRelationshipId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
)
from .enums import KnowledgeObjectType, RelationshipPredicate
from .value_objects import KnowledgeScope


# --- KnowledgeSource ----------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceRegistered(DomainEvent):
    source_id: KnowledgeSourceId
    scope: KnowledgeScope


@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceCurrentVersionSet(DomainEvent):
    source_id: KnowledgeSourceId
    version_id: KnowledgeSourceVersionId


# --- KnowledgeSourceVersion ---------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceVersionDrafted(DomainEvent):
    version_id: KnowledgeSourceVersionId
    source_id: KnowledgeSourceId
    scope: KnowledgeScope


@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceVersionSubmittedForReview(DomainEvent):
    version_id: KnowledgeSourceVersionId


@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceVersionApproved(DomainEvent):
    version_id: KnowledgeSourceVersionId


@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceVersionRejected(DomainEvent):
    version_id: KnowledgeSourceVersionId
    reason: str


@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceVersionPublished(DomainEvent):
    version_id: KnowledgeSourceVersionId
    source_id: KnowledgeSourceId
    effective_from: datetime


@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceVersionSuperseded(DomainEvent):
    version_id: KnowledgeSourceVersionId
    superseded_by_version_id: KnowledgeSourceVersionId


@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceVersionWithdrawn(DomainEvent):
    version_id: KnowledgeSourceVersionId
    reason: str


@dataclass(frozen=True, kw_only=True)
class KnowledgeSourceVersionArchived(DomainEvent):
    version_id: KnowledgeSourceVersionId


@dataclass(frozen=True, kw_only=True)
class KnowledgeDocumentAttached(DomainEvent):
    version_id: KnowledgeSourceVersionId
    document_id: KnowledgeDocumentId
    language: str


# --- CanonicalKnowledgeObject / KnowledgeObject -------------------------------------------
@dataclass(frozen=True, kw_only=True)
class CanonicalKnowledgeObjectStarted(DomainEvent):
    canonical_id: CanonicalKnowledgeObjectId
    object_type: KnowledgeObjectType
    source_id: KnowledgeSourceId


@dataclass(frozen=True, kw_only=True)
class KnowledgeObjectRevisionRegistered(DomainEvent):
    canonical_id: CanonicalKnowledgeObjectId
    object_id: KnowledgeObjectId


@dataclass(frozen=True, kw_only=True)
class KnowledgeObjectExtracted(DomainEvent):
    object_id: KnowledgeObjectId
    canonical_id: CanonicalKnowledgeObjectId
    object_type: KnowledgeObjectType
    source_version_id: KnowledgeSourceVersionId


@dataclass(frozen=True, kw_only=True)
class KnowledgeObjectSubmittedForReview(DomainEvent):
    object_id: KnowledgeObjectId


@dataclass(frozen=True, kw_only=True)
class KnowledgeObjectPublished(DomainEvent):
    object_id: KnowledgeObjectId


@dataclass(frozen=True, kw_only=True)
class KnowledgeObjectRejected(DomainEvent):
    object_id: KnowledgeObjectId
    reason: str


@dataclass(frozen=True, kw_only=True)
class KnowledgeObjectSuperseded(DomainEvent):
    object_id: KnowledgeObjectId
    superseded_by_object_id: KnowledgeObjectId


# --- KnowledgeRelationship ----------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class KnowledgeRelationshipAsserted(DomainEvent):
    relationship_id: KnowledgeRelationshipId
    predicate: RelationshipPredicate
    scope: KnowledgeScope


@dataclass(frozen=True, kw_only=True)
class KnowledgeRelationshipSubmittedForReview(DomainEvent):
    relationship_id: KnowledgeRelationshipId


@dataclass(frozen=True, kw_only=True)
class KnowledgeRelationshipPublished(DomainEvent):
    relationship_id: KnowledgeRelationshipId


@dataclass(frozen=True, kw_only=True)
class KnowledgeRelationshipRejected(DomainEvent):
    relationship_id: KnowledgeRelationshipId
    reason: str


@dataclass(frozen=True, kw_only=True)
class KnowledgeRelationshipSuperseded(DomainEvent):
    relationship_id: KnowledgeRelationshipId
    superseded_by_relationship_id: KnowledgeRelationshipId
