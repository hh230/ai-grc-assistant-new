"""Value objects for the Knowledge bounded context.

All are immutable (frozen) with value equality, and validate their own invariants in
``__post_init__`` so an invalid value object can never be constructed — including during
reconstruction. Cross-aggregate references are by typed id only.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from ..shared.identifiers import (
    ExtractionRunId,
    FrameworkControlId,
    FrameworkId,
    KnowledgeDocumentId,
    KnowledgeObjectId,
    KnowledgeSectionId,
    KnowledgeSourceVersionId,
    OrganizationId,
)
from ..shared.value_objects import Actor, Confidence
from .enums import (
    DerivationMethod,
    KnowledgeObjectType,
    KnowledgeScopeKind,
    RelationshipEndpointKind,
    SectionType,
)


@dataclass(frozen=True)
class KnowledgeScope:
    """Tenant scope of a knowledge entity: platform-global or a specific organization.

    Encodes the two-library model at the type level: ``GLOBAL`` knowledge is shared and
    carries no tenant; ``ORGANIZATION`` knowledge is isolated and must carry its tenant.
    """

    kind: KnowledgeScopeKind
    organization_id: OrganizationId | None = None

    def __post_init__(self) -> None:
        if self.kind is KnowledgeScopeKind.ORGANIZATION and self.organization_id is None:
            raise ValueError("ORGANIZATION scope requires an organization_id")
        if self.kind is KnowledgeScopeKind.GLOBAL and self.organization_id is not None:
            raise ValueError("GLOBAL scope must not carry an organization_id")

    @classmethod
    def global_(cls) -> KnowledgeScope:
        return cls(KnowledgeScopeKind.GLOBAL)

    @classmethod
    def for_organization(cls, organization_id: OrganizationId) -> KnowledgeScope:
        return cls(KnowledgeScopeKind.ORGANIZATION, organization_id)

    @property
    def is_global(self) -> bool:
        return self.kind is KnowledgeScopeKind.GLOBAL

    @property
    def is_organization(self) -> bool:
        return self.kind is KnowledgeScopeKind.ORGANIZATION


@dataclass(frozen=True)
class LocalizedText:
    """Multilingual text (e.g. Arabic + English) stored as ordered (language, text) pairs.

    The first entry is the default. Immutable and hashable (a tuple of pairs).
    """

    entries: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("LocalizedText must have at least one (language, text) entry")
        seen: set[str] = set()
        for language, text in self.entries:
            if not language or not language.strip():
                raise ValueError("LocalizedText language must be non-empty")
            if not text or not text.strip():
                raise ValueError("LocalizedText text must be non-empty")
            if language in seen:
                raise ValueError(f"Duplicate language in LocalizedText: {language!r}")
            seen.add(language)

    @classmethod
    def of(cls, language: str, text: str) -> LocalizedText:
        return cls(((language, text),))

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str]) -> LocalizedText:
        return cls(tuple(mapping.items()))

    def get(self, language: str) -> str | None:
        for lang, text in self.entries:
            if lang == language:
                return text
        return None

    @property
    def default(self) -> str:
        return self.entries[0][1]

    @property
    def languages(self) -> tuple[str, ...]:
        return tuple(language for language, _ in self.entries)


@dataclass(frozen=True)
class StructuralAnchor:
    """A stable, human-meaningful locator (e.g. Article 5(2), §A.8.1) that survives re-chunking.

    Because citations point at this anchor — not at a chunk id — they remain valid even when
    the corpus is later re-processed.
    """

    section_type: SectionType
    code: str
    path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("StructuralAnchor code must not be empty")

    def __str__(self) -> str:
        prefix = "/".join(self.path)
        return f"{prefix}/{self.code}" if prefix else self.code


@dataclass(frozen=True)
class PageRange:
    """An inclusive page span within a document (1-based)."""

    start_page: int
    end_page: int

    def __post_init__(self) -> None:
        if self.start_page < 1:
            raise ValueError("PageRange start_page must be >= 1")
        if self.end_page < self.start_page:
            raise ValueError("PageRange end_page must be >= start_page")


@dataclass(frozen=True)
class TextSpan:
    """A character offset range within a section's normalized text (half-open semantics)."""

    start_offset: int
    end_offset: int

    def __post_init__(self) -> None:
        if self.start_offset < 0:
            raise ValueError("TextSpan start_offset must be >= 0")
        if self.end_offset < self.start_offset:
            raise ValueError("TextSpan end_offset must be >= start_offset")

    @property
    def length(self) -> int:
        return self.end_offset - self.start_offset


@dataclass(frozen=True)
class ContentHash:
    """Integrity/dedup hash of a document's raw bytes."""

    algorithm: str
    value: str

    def __post_init__(self) -> None:
        if not self.algorithm.strip():
            raise ValueError("ContentHash algorithm must not be empty")
        if not self.value.strip():
            raise ValueError("ContentHash value must not be empty")


@dataclass(frozen=True)
class StorageLocator:
    """An opaque pointer to where raw bytes live (object-store URI). Never the bytes."""

    uri: str

    def __post_init__(self) -> None:
        if not self.uri.strip():
            raise ValueError("StorageLocator uri must not be empty")


@dataclass(frozen=True)
class Approval:
    """Records the human gate decision on publishing a version."""

    actor: Actor
    decided_at: datetime


@dataclass(frozen=True)
class ProvenanceRecord:
    """The intrinsic lineage carried by every knowledge object and relationship.

    Binds a fact to its exact origin (source version → document → section → span/page) and to
    the extraction run + processor versions that produced it, so any fact is independently
    verifiable and reproducible. The minimum provenance is the source version it came from.
    """

    source_version_id: KnowledgeSourceVersionId
    document_id: KnowledgeDocumentId | None = None
    section_id: KnowledgeSectionId | None = None
    anchor: StructuralAnchor | None = None
    text_span: TextSpan | None = None
    page_range: PageRange | None = None
    extraction_run_id: ExtractionRunId | None = None
    extractor_name: str | None = None
    extractor_version: str | None = None
    confidence: Confidence | None = None
    derivation: DerivationMethod = DerivationMethod.AUTOMATIC
    language: str | None = None

    def __post_init__(self) -> None:
        if self.extractor_name is not None and not self.extractor_name.strip():
            raise ValueError("ProvenanceRecord extractor_name, if provided, must not be empty")


@dataclass(frozen=True)
class RelationshipEndpoint:
    """A polymorphic graph endpoint: an internal object/section, or an external framework control.

    Exactly the fields matching ``kind`` are set; all others must be ``None``.
    """

    kind: RelationshipEndpointKind
    knowledge_object_id: KnowledgeObjectId | None = None
    section_id: KnowledgeSectionId | None = None
    framework_id: FrameworkId | None = None
    framework_control_id: FrameworkControlId | None = None

    def __post_init__(self) -> None:
        if self.kind is RelationshipEndpointKind.KNOWLEDGE_OBJECT:
            if self.knowledge_object_id is None:
                raise ValueError("KNOWLEDGE_OBJECT endpoint requires knowledge_object_id")
            if any((self.section_id, self.framework_id, self.framework_control_id)):
                raise ValueError("KNOWLEDGE_OBJECT endpoint must set only knowledge_object_id")
        elif self.kind is RelationshipEndpointKind.SECTION:
            if self.section_id is None:
                raise ValueError("SECTION endpoint requires section_id")
            if any((self.knowledge_object_id, self.framework_id, self.framework_control_id)):
                raise ValueError("SECTION endpoint must set only section_id")
        elif self.kind is RelationshipEndpointKind.FRAMEWORK_CONTROL:
            if self.framework_id is None or self.framework_control_id is None:
                raise ValueError(
                    "FRAMEWORK_CONTROL endpoint requires framework_id and framework_control_id"
                )
            if any((self.knowledge_object_id, self.section_id)):
                raise ValueError(
                    "FRAMEWORK_CONTROL endpoint must set only framework ids"
                )

    @classmethod
    def for_object(cls, knowledge_object_id: KnowledgeObjectId) -> RelationshipEndpoint:
        return cls(
            RelationshipEndpointKind.KNOWLEDGE_OBJECT,
            knowledge_object_id=knowledge_object_id,
        )

    @classmethod
    def for_section(cls, section_id: KnowledgeSectionId) -> RelationshipEndpoint:
        return cls(RelationshipEndpointKind.SECTION, section_id=section_id)

    @classmethod
    def for_framework_control(
        cls,
        framework_id: FrameworkId,
        framework_control_id: FrameworkControlId,
    ) -> RelationshipEndpoint:
        return cls(
            RelationshipEndpointKind.FRAMEWORK_CONTROL,
            framework_id=framework_id,
            framework_control_id=framework_control_id,
        )


# --- Type-specific payloads (a representative, extensible set) -----------------------------
# A KnowledgeObject may carry a structured payload of attributes specific to its type. Each
# concrete payload declares the KnowledgeObjectType it belongs to via OBJECT_TYPE, which the
# KnowledgeObject factory validates against the object's type.


@dataclass(frozen=True)
class KnowledgeObjectPayload:
    """Marker base for type-specific knowledge-object attributes."""

    OBJECT_TYPE: ClassVar[KnowledgeObjectType]


@dataclass(frozen=True)
class DefinitionPayload(KnowledgeObjectPayload):
    OBJECT_TYPE: ClassVar[KnowledgeObjectType] = KnowledgeObjectType.DEFINITION

    term: str
    scope_note: str | None = None

    def __post_init__(self) -> None:
        if not self.term.strip():
            raise ValueError("DefinitionPayload term must not be empty")


@dataclass(frozen=True)
class RequirementPayload(KnowledgeObjectPayload):
    OBJECT_TYPE: ClassVar[KnowledgeObjectType] = KnowledgeObjectType.REQUIREMENT

    code: str | None = None
    modal: str | None = None
    applicability: str | None = None


@dataclass(frozen=True)
class ControlPayload(KnowledgeObjectPayload):
    OBJECT_TYPE: ClassVar[KnowledgeObjectType] = KnowledgeObjectType.CONTROL

    code: str | None = None
    control_family: str | None = None


@dataclass(frozen=True)
class ObligationPayload(KnowledgeObjectPayload):
    OBJECT_TYPE: ClassVar[KnowledgeObjectType] = KnowledgeObjectType.OBLIGATION

    obligated_party: str | None = None
    trigger: str | None = None
    deadline: str | None = None
