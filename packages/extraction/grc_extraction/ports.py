"""The extraction engine's ports — the stable abstraction seams (hexagonal architecture).

Every concrete adapter (PDF parser, OCR, normalizer, segmenter, classifier, rule-based or
AI-assisted extractor, framework mapper, persistence) implements one of these. The engine
core depends only on these ports and never on any library or LLM SDK — that is what lets AI
plug in later without coupling the engine.

I/O-bearing operations are ``async`` (a rule-based implementation simply returns); pure
metadata accessors are sync. These are pure abstractions — no implementations here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from grc_domain.extraction import (
    CandidateRelationship,
    ExtractionCandidate,
    RawDocumentDescriptor,
)
from grc_domain.knowledge import ContentHash, DocumentFormat, KnowledgeObjectType, KnowledgeScope
from grc_domain.shared.value_objects import Confidence

from .artifacts import (
    CandidateSet,
    ClassificationResult,
    ExtractionContext,
    ExtractionResult,
    IngestionResult,
    NormalizedDocument,
    ParsedDocument,
    ScoringSignals,
    Segment,
    SegmentTree,
)
from .enums import ExtractorTechnique
from .profiles import ExtractionProfile


@dataclass(frozen=True)
class ExtractorDescriptor:
    """Plugin metadata an extractor exposes so the registry can index and a profile can
    select it. ``technique`` distinguishes rule-based from AI-assisted — but the engine
    treats both identically."""

    name: str
    version: str
    technique: ExtractorTechnique
    produces: frozenset[KnowledgeObjectType]
    supported_languages: tuple[str, ...] = ()
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ExtractorDescriptor name must not be empty")
        if not self.version.strip():
            raise ValueError("ExtractorDescriptor version must not be empty")
        if not self.produces:
            raise ValueError("ExtractorDescriptor must declare at least one produced type")

    @property
    def key(self) -> tuple[str, str]:
        return (self.name, self.version)


# --- intake / parse ------------------------------------------------------------------------
class DocumentAdapterPort(ABC):
    """Turns a raw document (by format) into a uniform ParsedDocument."""

    @abstractmethod
    def supports(self, document_format: DocumentFormat) -> bool: ...

    @abstractmethod
    async def parse(self, document: RawDocumentDescriptor) -> ParsedDocument: ...


class OcrPort(ABC):
    """Recognizes text + layout from a scanned/image document."""

    @abstractmethod
    async def recognize(self, document: RawDocumentDescriptor) -> ParsedDocument: ...


# --- normalize / segment / classify --------------------------------------------------------
class NormalizerPort(ABC):
    """Cleans and language-tags parsed content while preserving structure and offsets."""

    @abstractmethod
    async def normalize(
        self, document: ParsedDocument, *, language: str | None = None
    ) -> NormalizedDocument: ...


class SegmenterPort(ABC):
    """Recovers the document's logical skeleton using the profile's grammar."""

    @abstractmethod
    async def segment(
        self, document: NormalizedDocument, *, profile: ExtractionProfile
    ) -> SegmentTree: ...


class ClassifierPort(ABC):
    """Confirms the document type (and may refine segment roles) with a confidence."""

    @abstractmethod
    async def classify(
        self, document: NormalizedDocument, *, segments: SegmentTree | None = None
    ) -> ClassificationResult: ...


# --- extract -------------------------------------------------------------------------------
class ExtractorPort(ABC):
    """Produces candidate knowledge objects from one segment. Rule-based or AI-assisted —
    both implement this identical contract."""

    @property
    @abstractmethod
    def descriptor(self) -> ExtractorDescriptor: ...

    @abstractmethod
    async def extract(self, segment: Segment, context: ExtractionContext) -> CandidateSet: ...


class RelationshipExtractorPort(ABC):
    """Derives typed edges between candidates (structural / referential / semantic)."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    async def extract(
        self, candidates: tuple[ExtractionCandidate, ...], context: ExtractionContext
    ) -> tuple[CandidateRelationship, ...]: ...


# --- score / map ---------------------------------------------------------------------------
class ConfidenceScorerPort(ABC):
    """Combines signals into a final confidence for a candidate."""

    @abstractmethod
    async def score(
        self, candidate: ExtractionCandidate, *, signals: ScoringSignals
    ) -> Confidence: ...


class FrameworkMappingPort(ABC):
    """Maps a control/requirement candidate to Framework Engine controls as ``mapped_to``
    edges. References frameworks by id only — never a hardcoded framework name."""

    @abstractmethod
    async def map_candidate(
        self, candidate: ExtractionCandidate, context: ExtractionContext
    ) -> tuple[CandidateRelationship, ...]: ...


# --- persist (integration with the Knowledge Database) -------------------------------------
class KnowledgeIngestionPort(ABC):
    """The write contract to the Knowledge Domain. Implementations persist atomically through
    the existing Unit of Work + transactional outbox — the engine never touches the database."""

    @abstractmethod
    async def find_existing(
        self, scope: KnowledgeScope, content_hash: ContentHash
    ) -> IngestionResult | None: ...

    @abstractmethod
    async def persist_result(self, result: ExtractionResult) -> IngestionResult: ...
