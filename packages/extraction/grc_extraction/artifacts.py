"""Working artifacts passed between pipeline ports, plus the integration payloads.

These are immutable value objects (data carriers). They reuse the Knowledge Domain's value
objects so the integration layer maps the engine's output onto KnowledgeObject /
KnowledgeRelationship / KnowledgeDocument / KnowledgeSection with no translation logic.
"""
from __future__ import annotations

from dataclasses import dataclass

from grc_domain.extraction import CandidateRelationship, ExtractionCandidate
from grc_domain.knowledge import (
    ContentHash,
    DocumentFormat,
    DocumentType,
    KnowledgeScope,
    LocalizedText,
    PageRange,
    StorageLocator,
    StructuralAnchor,
    TextSpan,
)
from grc_domain.shared.identifiers import (
    ExtractionRunId,
    KnowledgeObjectId,
    KnowledgeRelationshipId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
)
from grc_domain.shared.value_objects import Confidence

from .enums import BlockKind, SegmentRole
from .profiles import ExtractionProfile


# --- parse / normalize ---------------------------------------------------------------------
@dataclass(frozen=True)
class LayoutBlock:
    """A unit of parsed content with its structural signal and page position."""

    text: str
    page_number: int
    kind: BlockKind = BlockKind.PARAGRAPH
    order: int = 0

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("LayoutBlock text must not be empty")
        if self.page_number < 1:
            raise ValueError("LayoutBlock page_number must be >= 1")
        if self.order < 0:
            raise ValueError("LayoutBlock order must be >= 0")


@dataclass(frozen=True)
class ParsedDocument:
    """The uniform output of any DocumentAdapterPort / OcrPort (format-agnostic)."""

    blocks: tuple[LayoutBlock, ...]
    document_format: DocumentFormat
    language: str | None = None
    page_count: int | None = None
    ocr_applied: bool = False
    parser_name: str | None = None
    parser_version: str | None = None

    @property
    def full_text(self) -> str:
        return "\n".join(block.text for block in self.blocks)


@dataclass(frozen=True)
class NormalizedDocument:
    """Cleaned, language-tagged content with structure preserved for segmentation."""

    blocks: tuple[LayoutBlock, ...]
    language: str | None = None
    normalizer_name: str | None = None
    normalizer_version: str | None = None

    @property
    def full_text(self) -> str:
        return "\n".join(block.text for block in self.blocks)


# --- segment / classify --------------------------------------------------------------------
@dataclass(frozen=True)
class Segment:
    """A node of the document's logical skeleton — the citation anchor + its text."""

    anchor: StructuralAnchor
    text: str
    role: SegmentRole = SegmentRole.OTHER
    text_span: TextSpan | None = None
    page_range: PageRange | None = None
    position: int = 0
    parent_index: int | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Segment text must not be empty")
        if self.position < 0:
            raise ValueError("Segment position must be >= 0")
        if self.parent_index is not None and self.parent_index < 0:
            raise ValueError("Segment parent_index must be >= 0")


@dataclass(frozen=True)
class SegmentTree:
    """The ordered, hierarchical segments of one document. ``parent_index`` references a
    position in ``segments``."""

    segments: tuple[Segment, ...] = ()

    def __post_init__(self) -> None:
        count = len(self.segments)
        for index, segment in enumerate(self.segments):
            if segment.parent_index is not None:
                if segment.parent_index >= count:
                    raise ValueError("Segment parent_index is out of range")
                if segment.parent_index == index:
                    raise ValueError("Segment cannot be its own parent")

    @property
    def roots(self) -> tuple[Segment, ...]:
        return tuple(s for s in self.segments if s.parent_index is None)

    def children_of(self, index: int) -> tuple[Segment, ...]:
        return tuple(s for s in self.segments if s.parent_index == index)


@dataclass(frozen=True)
class ClassificationResult:
    """The classifier's confirmation of document type with a confidence."""

    document_type: DocumentType
    confidence: Confidence


# --- extract / score -----------------------------------------------------------------------
@dataclass(frozen=True)
class ExtractionContext:
    """Everything an extractor needs about the run, beyond the segment itself."""

    scope: KnowledgeScope
    source_id: KnowledgeSourceId
    version_id: KnowledgeSourceVersionId
    document_type: DocumentType
    profile: ExtractionProfile
    language: str | None = None
    defined_terms: tuple[str, ...] = ()
    sibling_segments: tuple[Segment, ...] = ()


@dataclass(frozen=True)
class CandidateSet:
    """The objects an ExtractorPort produced for one segment."""

    objects: tuple[ExtractionCandidate, ...] = ()

    @property
    def is_empty(self) -> bool:
        return len(self.objects) == 0

    def __len__(self) -> int:
        return len(self.objects)


@dataclass(frozen=True)
class ScoringSignals:
    """Signals combined by a ConfidenceScorerPort into a final confidence."""

    extractor_confidence: Confidence | None = None
    classification_confidence: Confidence | None = None
    corroborations: int = 0
    structural_certainty: float | None = None

    def __post_init__(self) -> None:
        if self.corroborations < 0:
            raise ValueError("ScoringSignals corroborations must be >= 0")
        if self.structural_certainty is not None and not 0.0 <= self.structural_certainty <= 1.0:
            raise ValueError("ScoringSignals structural_certainty must be within [0, 1]")


# --- persistence integration payloads ------------------------------------------------------
@dataclass(frozen=True)
class SectionPlan:
    """A section to be created under a document at persist time."""

    anchor: StructuralAnchor
    position: int = 0
    title: LocalizedText | None = None
    page_range: PageRange | None = None
    parent_index: int | None = None

    def __post_init__(self) -> None:
        if self.position < 0:
            raise ValueError("SectionPlan position must be >= 0")


@dataclass(frozen=True)
class DocumentPlan:
    """A document manifestation (with its sections) to be attached to the draft version."""

    language: str
    document_format: DocumentFormat
    storage_locator: StorageLocator
    content_hash: ContentHash
    sections: tuple[SectionPlan, ...] = ()
    is_translation: bool = False

    def __post_init__(self) -> None:
        if not self.language.strip():
            raise ValueError("DocumentPlan language must not be empty")


@dataclass(frozen=True)
class ExtractionResult:
    """The complete output of a run, handed to KnowledgeIngestionPort for atomic persistence."""

    run_id: ExtractionRunId
    scope: KnowledgeScope
    source_id: KnowledgeSourceId
    version_id: KnowledgeSourceVersionId
    documents: tuple[DocumentPlan, ...] = ()
    objects: tuple[ExtractionCandidate, ...] = ()
    relationships: tuple[CandidateRelationship, ...] = ()
    pipeline_version: str | None = None


@dataclass(frozen=True)
class IngestionResult:
    """The ids persisted by KnowledgeIngestionPort (for the run to record)."""

    object_ids: tuple[KnowledgeObjectId, ...] = ()
    relationship_ids: tuple[KnowledgeRelationshipId, ...] = ()
    version_id: KnowledgeSourceVersionId | None = None
