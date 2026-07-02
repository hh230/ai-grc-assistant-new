"""Aggregates and entities for the Knowledge bounded context — the canonical structured
knowledge model (the heart of the platform).

Contents:
- ``KnowledgeSection`` / ``KnowledgeDocument`` — child entities of a source version.
- ``KnowledgeSource`` — the stable logical work (identity + facets) [aggregate root].
- ``KnowledgeSourceVersion`` — an immutable, effective-dated version that owns its
  documents and enforces the governance lifecycle [aggregate root].
- ``CanonicalKnowledgeObject`` — the lineage identity grouping an object's revisions
  [aggregate root].
- ``KnowledgeObject`` — one immutable, version-pinned extracted fact [aggregate root].
- ``KnowledgeRelationship`` — a typed edge between objects/sections/framework controls
  [aggregate root].

Pure domain logic: no persistence, infrastructure, RAG, embeddings, or AI. Invariants and
events are recorded by factory methods and lifecycle transitions; the plain constructor is
the trusted reconstruction path and records nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..shared.entity import AggregateRoot, Entity, utcnow
from ..shared.enums import DataClassification
from ..shared.exceptions import InvariantViolation
from ..shared.identifiers import (
    CanonicalKnowledgeObjectId,
    FrameworkId,
    KnowledgeDocumentId,
    KnowledgeObjectId,
    KnowledgeRelationshipId,
    KnowledgeSectionId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
)
from ..shared.value_objects import Actor, Confidence, DateRange, SemanticVersion
from .enums import (
    CurationStatus,
    DocumentFormat,
    DocumentType,
    KnowledgeDomain,
    KnowledgeObjectType,
    NormativeStrength,
    RelationshipPredicate,
    VersionStatus,
)
from .events import (
    CanonicalKnowledgeObjectStarted,
    KnowledgeDocumentAttached,
    KnowledgeObjectExtracted,
    KnowledgeObjectPublished,
    KnowledgeObjectRejected,
    KnowledgeObjectRevisionRegistered,
    KnowledgeObjectSubmittedForReview,
    KnowledgeObjectSuperseded,
    KnowledgeRelationshipAsserted,
    KnowledgeRelationshipPublished,
    KnowledgeRelationshipRejected,
    KnowledgeRelationshipSubmittedForReview,
    KnowledgeRelationshipSuperseded,
    KnowledgeSourceCurrentVersionSet,
    KnowledgeSourceRegistered,
    KnowledgeSourceVersionApproved,
    KnowledgeSourceVersionArchived,
    KnowledgeSourceVersionDrafted,
    KnowledgeSourceVersionPublished,
    KnowledgeSourceVersionRejected,
    KnowledgeSourceVersionSubmittedForReview,
    KnowledgeSourceVersionSuperseded,
    KnowledgeSourceVersionWithdrawn,
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
from .value_objects import (
    Approval,
    ContentHash,
    KnowledgeObjectPayload,
    KnowledgeScope,
    LocalizedText,
    PageRange,
    ProvenanceRecord,
    RelationshipEndpoint,
    StorageLocator,
    StructuralAnchor,
)

# --- Lifecycle transition maps (status -> reachable statuses) ------------------------------

_VERSION_TRANSITIONS: dict[VersionStatus, frozenset[VersionStatus]] = {
    VersionStatus.DRAFT: frozenset({VersionStatus.IN_REVIEW}),
    VersionStatus.IN_REVIEW: frozenset(
        {VersionStatus.APPROVED, VersionStatus.REJECTED, VersionStatus.DRAFT}
    ),
    VersionStatus.APPROVED: frozenset({VersionStatus.PUBLISHED, VersionStatus.REJECTED}),
    VersionStatus.PUBLISHED: frozenset({VersionStatus.SUPERSEDED, VersionStatus.WITHDRAWN}),
    VersionStatus.SUPERSEDED: frozenset({VersionStatus.ARCHIVED}),
    VersionStatus.WITHDRAWN: frozenset({VersionStatus.ARCHIVED}),
    VersionStatus.REJECTED: frozenset({VersionStatus.ARCHIVED}),
    VersionStatus.ARCHIVED: frozenset(),
}

# A version's content (its documents) may only change while it is still being authored.
_CONTENT_MUTABLE_VERSION_STATUSES: frozenset[VersionStatus] = frozenset(
    {VersionStatus.DRAFT, VersionStatus.IN_REVIEW}
)

# Curation lifecycle shared by knowledge objects and relationships.
_CURATION_TRANSITIONS: dict[CurationStatus, frozenset[CurationStatus]] = {
    CurationStatus.EXTRACTED: frozenset({CurationStatus.IN_REVIEW, CurationStatus.REJECTED}),
    CurationStatus.IN_REVIEW: frozenset(
        {CurationStatus.PUBLISHED, CurationStatus.REJECTED, CurationStatus.EXTRACTED}
    ),
    CurationStatus.PUBLISHED: frozenset({CurationStatus.SUPERSEDED}),
    CurationStatus.SUPERSEDED: frozenset(),
    CurationStatus.REJECTED: frozenset(),
}


# --- Child entities ------------------------------------------------------------------------


@dataclass(eq=False)
class KnowledgeSection(Entity):
    """A structural unit (article/clause/section) within a document — the citation anchor.

    Phase 1 models structure only; extracted text and chunks attach in a later phase.
    """

    id: KnowledgeSectionId
    document_id: KnowledgeDocumentId
    anchor: StructuralAnchor
    title: LocalizedText | None = None
    position: int = 0
    page_range: PageRange | None = None
    parent_section_id: KnowledgeSectionId | None = None

    @classmethod
    def create(
        cls,
        *,
        id: KnowledgeSectionId,
        document_id: KnowledgeDocumentId,
        anchor: StructuralAnchor,
        title: LocalizedText | None = None,
        position: int = 0,
        page_range: PageRange | None = None,
        parent_section_id: KnowledgeSectionId | None = None,
    ) -> KnowledgeSection:
        if position < 0:
            raise ValueError("KnowledgeSection position must be >= 0")
        return cls(
            id=id,
            document_id=document_id,
            anchor=anchor,
            title=title,
            position=position,
            page_range=page_range,
            parent_section_id=parent_section_id,
        )


@dataclass(eq=False)
class KnowledgeDocument(Entity):
    """A physical manifestation of a version (one language/format). Holds a pointer to the
    raw bytes, never the bytes themselves."""

    id: KnowledgeDocumentId
    version_id: KnowledgeSourceVersionId
    language: str
    document_format: DocumentFormat
    storage_locator: StorageLocator
    content_hash: ContentHash
    is_translation: bool = False
    translation_of_document_id: KnowledgeDocumentId | None = None
    page_count: int | None = None
    byte_size: int | None = None
    sections: list[KnowledgeSection] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        id: KnowledgeDocumentId,
        version_id: KnowledgeSourceVersionId,
        language: str,
        document_format: DocumentFormat,
        storage_locator: StorageLocator,
        content_hash: ContentHash,
        is_translation: bool = False,
        translation_of_document_id: KnowledgeDocumentId | None = None,
        page_count: int | None = None,
        byte_size: int | None = None,
    ) -> KnowledgeDocument:
        if not language.strip():
            raise ValueError("KnowledgeDocument language must not be empty")
        if is_translation and translation_of_document_id is None:
            raise ValueError("A translation must reference translation_of_document_id")
        if page_count is not None and page_count < 0:
            raise ValueError("KnowledgeDocument page_count must be >= 0")
        if byte_size is not None and byte_size < 0:
            raise ValueError("KnowledgeDocument byte_size must be >= 0")
        return cls(
            id=id,
            version_id=version_id,
            language=language,
            document_format=document_format,
            storage_locator=storage_locator,
            content_hash=content_hash,
            is_translation=is_translation,
            translation_of_document_id=translation_of_document_id,
            page_count=page_count,
            byte_size=byte_size,
        )

    def add_section(self, section: KnowledgeSection) -> None:
        if section.document_id != self.id:
            raise InvariantViolation("Section.document_id does not match this document")
        if any(existing.id == section.id for existing in self.sections):
            raise InvariantViolation(f"Section {section.id} already added")
        self.sections.append(section)
        self._touch()

    def section(self, section_id: KnowledgeSectionId) -> KnowledgeSection:
        for existing in self.sections:
            if existing.id == section_id:
                return existing
        raise KnowledgeSectionNotFound(str(section_id))


# --- Aggregate roots -----------------------------------------------------------------------


@dataclass(kw_only=True, eq=False)
class KnowledgeSource(AggregateRoot):
    """The stable logical identity of a body of knowledge (a law, standard, policy...).

    Deliberately small: identity + facets + a pointer to the in-force version. Versions are
    separate aggregates so a source can accrue many versions without growing.
    """

    id: KnowledgeSourceId
    scope: KnowledgeScope
    short_code: str
    title: LocalizedText
    authority: str
    jurisdiction: str
    knowledge_domain: KnowledgeDomain
    document_type: DocumentType
    classification: DataClassification = DataClassification.CONFIDENTIAL
    framework_refs: tuple[FrameworkId, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    canonical_languages: tuple[str, ...] = field(default_factory=tuple)
    steward: Actor | None = None
    current_version_id: KnowledgeSourceVersionId | None = None

    @classmethod
    def register(
        cls,
        *,
        id: KnowledgeSourceId,
        scope: KnowledgeScope,
        short_code: str,
        title: LocalizedText,
        authority: str,
        jurisdiction: str,
        knowledge_domain: KnowledgeDomain,
        document_type: DocumentType,
        classification: DataClassification = DataClassification.CONFIDENTIAL,
        framework_refs: tuple[FrameworkId, ...] = (),
        tags: tuple[str, ...] = (),
        canonical_languages: tuple[str, ...] = (),
        steward: Actor | None = None,
    ) -> KnowledgeSource:
        if not short_code.strip():
            raise ValueError("KnowledgeSource short_code must not be empty")
        if not authority.strip():
            raise ValueError("KnowledgeSource authority must not be empty")
        if not jurisdiction.strip():
            raise ValueError("KnowledgeSource jurisdiction must not be empty")
        source = cls(
            id=id,
            scope=scope,
            short_code=short_code.strip(),
            title=title,
            authority=authority.strip(),
            jurisdiction=jurisdiction.strip(),
            knowledge_domain=knowledge_domain,
            document_type=document_type,
            classification=classification,
            framework_refs=tuple(framework_refs),
            tags=tuple(tags),
            canonical_languages=tuple(canonical_languages),
            steward=steward,
        )
        source._record_event(KnowledgeSourceRegistered(source_id=id, scope=scope))
        return source

    def set_current_version(self, version_id: KnowledgeSourceVersionId) -> None:
        self.current_version_id = version_id
        self._record_event(
            KnowledgeSourceCurrentVersionSet(source_id=self.id, version_id=version_id)
        )

    def add_framework_ref(self, framework_id: FrameworkId) -> None:
        if framework_id not in self.framework_refs:
            self.framework_refs = (*self.framework_refs, framework_id)
            self._touch()

    def add_tag(self, tag: str) -> None:
        cleaned = tag.strip()
        if cleaned and cleaned not in self.tags:
            self.tags = (*self.tags, cleaned)
            self._touch()

    def set_steward(self, steward: Actor) -> None:
        self.steward = steward
        self._touch()

    def reclassify(self, classification: DataClassification) -> None:
        self.classification = classification
        self._touch()


@dataclass(kw_only=True, eq=False)
class KnowledgeSourceVersion(AggregateRoot):
    """An immutable, effective-dated version of a source. Owns its documents and enforces the
    governance lifecycle (Draft -> In Review -> Approved -> Published -> Superseded/Withdrawn
    -> Archived). Content is frozen once Published; publishing requires a human approval gate
    and at least one document."""

    id: KnowledgeSourceVersionId
    source_id: KnowledgeSourceId
    scope: KnowledgeScope
    version_label: str
    status: VersionStatus = VersionStatus.DRAFT
    semantic_version: SemanticVersion | None = None
    effective_range: DateRange | None = None
    publication_date: datetime | None = None
    official_citation: str | None = None
    supersedes_version_id: KnowledgeSourceVersionId | None = None
    superseded_by_version_id: KnowledgeSourceVersionId | None = None
    amendment_of_version_id: KnowledgeSourceVersionId | None = None
    change_summary: LocalizedText | None = None
    language_set: tuple[str, ...] = field(default_factory=tuple)
    approval: Approval | None = None
    documents: list[KnowledgeDocument] = field(default_factory=list)

    @classmethod
    def draft(
        cls,
        *,
        id: KnowledgeSourceVersionId,
        source_id: KnowledgeSourceId,
        scope: KnowledgeScope,
        version_label: str,
        semantic_version: SemanticVersion | None = None,
        official_citation: str | None = None,
        change_summary: LocalizedText | None = None,
        language_set: tuple[str, ...] = (),
        supersedes_version_id: KnowledgeSourceVersionId | None = None,
        amendment_of_version_id: KnowledgeSourceVersionId | None = None,
    ) -> KnowledgeSourceVersion:
        if not version_label.strip():
            raise ValueError("KnowledgeSourceVersion version_label must not be empty")
        version = cls(
            id=id,
            source_id=source_id,
            scope=scope,
            version_label=version_label.strip(),
            semantic_version=semantic_version,
            official_citation=official_citation,
            change_summary=change_summary,
            language_set=tuple(language_set),
            supersedes_version_id=supersedes_version_id,
            amendment_of_version_id=amendment_of_version_id,
        )
        version._record_event(
            KnowledgeSourceVersionDrafted(version_id=id, source_id=source_id, scope=scope)
        )
        return version

    # ---- lifecycle helpers ----
    def _transition(self, target: VersionStatus) -> None:
        if target not in _VERSION_TRANSITIONS[self.status]:
            raise IllegalVersionTransition(
                f"Cannot move version from {self.status.value} to {target.value}"
            )
        self.status = target

    # ---- content (only while authoring) ----
    def attach_document(self, document: KnowledgeDocument) -> None:
        if self.status not in _CONTENT_MUTABLE_VERSION_STATUSES:
            raise VersionImmutable(
                f"Cannot attach a document to a version in {self.status.value} state"
            )
        if document.version_id != self.id:
            raise InvariantViolation("Document.version_id does not match this version")
        if any(existing.id == document.id for existing in self.documents):
            raise InvariantViolation(f"Document {document.id} already attached")
        self.documents.append(document)
        self._touch()
        self._record_event(
            KnowledgeDocumentAttached(
                version_id=self.id, document_id=document.id, language=document.language
            )
        )

    def document(self, document_id: KnowledgeDocumentId) -> KnowledgeDocument:
        for existing in self.documents:
            if existing.id == document_id:
                return existing
        raise KnowledgeDocumentNotFound(str(document_id))

    # ---- governance lifecycle ----
    def submit_for_review(self) -> None:
        self._transition(VersionStatus.IN_REVIEW)
        self._record_event(KnowledgeSourceVersionSubmittedForReview(version_id=self.id))

    def return_to_draft(self) -> None:
        self._transition(VersionStatus.DRAFT)

    def approve(self, *, approver: Actor) -> None:
        self._transition(VersionStatus.APPROVED)
        self.approval = Approval(actor=approver, decided_at=utcnow())
        self._record_event(KnowledgeSourceVersionApproved(version_id=self.id))

    def reject(self, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Rejection reason must not be empty")
        self._transition(VersionStatus.REJECTED)
        self._record_event(
            KnowledgeSourceVersionRejected(version_id=self.id, reason=reason)
        )

    def publish(self, *, effective_from: datetime) -> None:
        # Preconditions checked before any state mutation so a rejected publish is a no-op.
        if self.approval is None:
            raise PublishRequiresApproval(
                "A version requires a recorded approval before it can be published"
            )
        if not self.documents:
            raise VersionRequiresDocument(
                "A version requires at least one document before publishing"
            )
        self._transition(VersionStatus.PUBLISHED)
        self.publication_date = utcnow()
        self.effective_range = DateRange(start=effective_from)
        self._record_event(
            KnowledgeSourceVersionPublished(
                version_id=self.id, source_id=self.source_id, effective_from=effective_from
            )
        )

    def supersede(self, *, superseded_by_version_id: KnowledgeSourceVersionId) -> None:
        self._transition(VersionStatus.SUPERSEDED)
        self.superseded_by_version_id = superseded_by_version_id
        if self.effective_range is not None and self.effective_range.end is None:
            self.effective_range = DateRange(start=self.effective_range.start, end=utcnow())
        self._record_event(
            KnowledgeSourceVersionSuperseded(
                version_id=self.id, superseded_by_version_id=superseded_by_version_id
            )
        )

    def withdraw(self, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Withdrawal reason must not be empty")
        self._transition(VersionStatus.WITHDRAWN)
        self._record_event(
            KnowledgeSourceVersionWithdrawn(version_id=self.id, reason=reason)
        )

    def archive(self) -> None:
        self._transition(VersionStatus.ARCHIVED)
        self._record_event(KnowledgeSourceVersionArchived(version_id=self.id))

    # ---- queries ----
    def applies_at(self, moment: datetime) -> bool:
        """Whether this version is the in-force knowledge at a given point in time."""
        return (
            self.status is VersionStatus.PUBLISHED
            and self.effective_range is not None
            and self.effective_range.contains(moment)
        )

    @property
    def is_content_mutable(self) -> bool:
        return self.status in _CONTENT_MUTABLE_VERSION_STATUSES


@dataclass(kw_only=True, eq=False)
class CanonicalKnowledgeObject(AggregateRoot):
    """The stable lineage identity that groups all revisions of a logical knowledge object
    across source versions (e.g. 'Requirement A.8.1' as it evolved between editions)."""

    id: CanonicalKnowledgeObjectId
    scope: KnowledgeScope
    object_type: KnowledgeObjectType
    source_id: KnowledgeSourceId
    stable_key: str
    current_revision_id: KnowledgeObjectId | None = None
    revision_ids: list[KnowledgeObjectId] = field(default_factory=list)

    @classmethod
    def start(
        cls,
        *,
        id: CanonicalKnowledgeObjectId,
        scope: KnowledgeScope,
        object_type: KnowledgeObjectType,
        source_id: KnowledgeSourceId,
        stable_key: str,
    ) -> CanonicalKnowledgeObject:
        if not stable_key.strip():
            raise ValueError("CanonicalKnowledgeObject stable_key must not be empty")
        canonical = cls(
            id=id,
            scope=scope,
            object_type=object_type,
            source_id=source_id,
            stable_key=stable_key.strip(),
        )
        canonical._record_event(
            CanonicalKnowledgeObjectStarted(
                canonical_id=id, object_type=object_type, source_id=source_id
            )
        )
        return canonical

    def register_revision(
        self, object_id: KnowledgeObjectId, *, make_current: bool = True
    ) -> None:
        if object_id not in self.revision_ids:
            self.revision_ids.append(object_id)
        if make_current:
            self.current_revision_id = object_id
        self._touch()
        self._record_event(
            KnowledgeObjectRevisionRegistered(canonical_id=self.id, object_id=object_id)
        )

    def set_current_revision(self, object_id: KnowledgeObjectId) -> None:
        if object_id not in self.revision_ids:
            raise InvariantViolation(
                "Cannot set current revision to an object that is not a registered revision"
            )
        self.current_revision_id = object_id
        self._touch()


@dataclass(kw_only=True, eq=False)
class KnowledgeObject(AggregateRoot):
    """One immutable, version-pinned extracted fact (definition, requirement, control,
    obligation, risk, ...). Carries intrinsic provenance and moves through the curation
    lifecycle. Corrections create a new revision and supersede — never an in-place edit."""

    id: KnowledgeObjectId
    canonical_id: CanonicalKnowledgeObjectId
    scope: KnowledgeScope
    object_type: KnowledgeObjectType
    source_version_id: KnowledgeSourceVersionId
    verbatim_text: str
    provenance: ProvenanceRecord
    section_id: KnowledgeSectionId | None = None
    normalized_statement: str | None = None
    normative_strength: NormativeStrength = NormativeStrength.INFORMATIVE
    language: str | None = None
    party_role: str | None = None
    confidence: Confidence | None = None
    status: CurationStatus = CurationStatus.EXTRACTED
    payload: KnowledgeObjectPayload | None = None
    supersedes_object_id: KnowledgeObjectId | None = None
    superseded_by_object_id: KnowledgeObjectId | None = None

    @classmethod
    def extract(
        cls,
        *,
        id: KnowledgeObjectId,
        canonical_id: CanonicalKnowledgeObjectId,
        scope: KnowledgeScope,
        object_type: KnowledgeObjectType,
        source_version_id: KnowledgeSourceVersionId,
        verbatim_text: str,
        provenance: ProvenanceRecord,
        section_id: KnowledgeSectionId | None = None,
        normalized_statement: str | None = None,
        normative_strength: NormativeStrength = NormativeStrength.INFORMATIVE,
        language: str | None = None,
        party_role: str | None = None,
        confidence: Confidence | None = None,
        payload: KnowledgeObjectPayload | None = None,
        supersedes_object_id: KnowledgeObjectId | None = None,
    ) -> KnowledgeObject:
        if not verbatim_text.strip():
            raise ValueError("KnowledgeObject verbatim_text must not be empty")
        if provenance.source_version_id != source_version_id:
            raise InvariantViolation(
                "provenance.source_version_id must match the object's source_version_id"
            )
        if payload is not None:
            declared = getattr(type(payload), "OBJECT_TYPE", None)
            if declared is None:
                raise InvariantViolation(
                    "payload must be a concrete KnowledgeObjectPayload declaring OBJECT_TYPE"
                )
            if declared != object_type:
                raise InvariantViolation(
                    f"payload type {declared.value} does not match object_type "
                    f"{object_type.value}"
                )
        obj = cls(
            id=id,
            canonical_id=canonical_id,
            scope=scope,
            object_type=object_type,
            source_version_id=source_version_id,
            verbatim_text=verbatim_text,
            provenance=provenance,
            section_id=section_id,
            normalized_statement=normalized_statement,
            normative_strength=normative_strength,
            language=language,
            party_role=party_role,
            confidence=confidence,
            payload=payload,
            supersedes_object_id=supersedes_object_id,
        )
        obj._record_event(
            KnowledgeObjectExtracted(
                object_id=id,
                canonical_id=canonical_id,
                object_type=object_type,
                source_version_id=source_version_id,
            )
        )
        return obj

    def _transition(self, target: CurationStatus) -> None:
        if target not in _CURATION_TRANSITIONS[self.status]:
            raise IllegalKnowledgeObjectTransition(
                f"Cannot move knowledge object from {self.status.value} to {target.value}"
            )
        self.status = target

    def submit_for_review(self) -> None:
        self._transition(CurationStatus.IN_REVIEW)
        self._record_event(KnowledgeObjectSubmittedForReview(object_id=self.id))

    def return_to_extracted(self) -> None:
        self._transition(CurationStatus.EXTRACTED)

    def publish(self) -> None:
        self._transition(CurationStatus.PUBLISHED)
        self._record_event(KnowledgeObjectPublished(object_id=self.id))

    def reject(self, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Rejection reason must not be empty")
        self._transition(CurationStatus.REJECTED)
        self._record_event(KnowledgeObjectRejected(object_id=self.id, reason=reason))

    def supersede(self, *, superseded_by_object_id: KnowledgeObjectId) -> None:
        self._transition(CurationStatus.SUPERSEDED)
        self.superseded_by_object_id = superseded_by_object_id
        self._record_event(
            KnowledgeObjectSuperseded(
                object_id=self.id, superseded_by_object_id=superseded_by_object_id
            )
        )

    @property
    def is_published(self) -> bool:
        return self.status is CurationStatus.PUBLISHED


@dataclass(kw_only=True, eq=False)
class KnowledgeRelationship(AggregateRoot):
    """A typed edge of the knowledge graph: subject --predicate--> target, where endpoints are
    knowledge objects, sections, or external framework controls. Provenance-bearing and
    version-pinned; immutable once published, superseded on change."""

    id: KnowledgeRelationshipId
    scope: KnowledgeScope
    predicate: RelationshipPredicate
    subject: RelationshipEndpoint
    target: RelationshipEndpoint
    provenance: ProvenanceRecord
    version_pin: KnowledgeSourceVersionId | None = None
    effective_range: DateRange | None = None
    confidence: Confidence | None = None
    status: CurationStatus = CurationStatus.EXTRACTED
    supersedes_relationship_id: KnowledgeRelationshipId | None = None
    superseded_by_relationship_id: KnowledgeRelationshipId | None = None

    @classmethod
    def declare(
        cls,
        *,
        id: KnowledgeRelationshipId,
        scope: KnowledgeScope,
        predicate: RelationshipPredicate,
        subject: RelationshipEndpoint,
        target: RelationshipEndpoint,
        provenance: ProvenanceRecord,
        version_pin: KnowledgeSourceVersionId | None = None,
        effective_range: DateRange | None = None,
        confidence: Confidence | None = None,
        supersedes_relationship_id: KnowledgeRelationshipId | None = None,
    ) -> KnowledgeRelationship:
        if subject == target:
            raise SelfReferentialRelationship(
                "A relationship cannot connect an endpoint to itself"
            )
        relationship = cls(
            id=id,
            scope=scope,
            predicate=predicate,
            subject=subject,
            target=target,
            provenance=provenance,
            version_pin=version_pin,
            effective_range=effective_range,
            confidence=confidence,
            supersedes_relationship_id=supersedes_relationship_id,
        )
        relationship._record_event(
            KnowledgeRelationshipAsserted(relationship_id=id, predicate=predicate, scope=scope)
        )
        return relationship

    def _transition(self, target: CurationStatus) -> None:
        if target not in _CURATION_TRANSITIONS[self.status]:
            raise IllegalRelationshipTransition(
                f"Cannot move relationship from {self.status.value} to {target.value}"
            )
        self.status = target

    def submit_for_review(self) -> None:
        self._transition(CurationStatus.IN_REVIEW)
        self._record_event(KnowledgeRelationshipSubmittedForReview(relationship_id=self.id))

    def publish(self) -> None:
        self._transition(CurationStatus.PUBLISHED)
        self._record_event(KnowledgeRelationshipPublished(relationship_id=self.id))

    def reject(self, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Rejection reason must not be empty")
        self._transition(CurationStatus.REJECTED)
        self._record_event(
            KnowledgeRelationshipRejected(relationship_id=self.id, reason=reason)
        )

    def supersede(self, *, superseded_by_relationship_id: KnowledgeRelationshipId) -> None:
        self._transition(CurationStatus.SUPERSEDED)
        self.superseded_by_relationship_id = superseded_by_relationship_id
        self._record_event(
            KnowledgeRelationshipSuperseded(
                relationship_id=self.id,
                superseded_by_relationship_id=superseded_by_relationship_id,
            )
        )

    @property
    def is_published(self) -> bool:
        return self.status is CurationStatus.PUBLISHED
