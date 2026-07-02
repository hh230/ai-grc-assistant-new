"""grc_extraction — the Knowledge Extraction Engine's application/abstraction layer.

This package holds the engine's plugin architecture: the ports (stable seams), the working
artifacts that flow between them, the extraction profiles (config/data), and the registries
that resolve plugins. Everything here is a **pure abstraction** — there are no document
parsers, OCR, AI models, LLM calls, persistence, or other infrastructure adapters. Concrete
adapters implement these ports in outer infrastructure packages.

It depends only on ``grc_domain`` (the ``extraction`` and ``knowledge`` contexts).
"""
from __future__ import annotations

from .artifacts import (
    CandidateSet,
    ClassificationResult,
    DocumentPlan,
    ExtractionContext,
    ExtractionResult,
    IngestionResult,
    LayoutBlock,
    NormalizedDocument,
    ParsedDocument,
    ScoringSignals,
    SectionPlan,
    Segment,
    SegmentTree,
)
from .engine import (
    ExtractionPipeline,
    PipelineOutcome,
    PipelinePorts,
    StageExecutionIdFactory,
)
from .enums import BlockKind, ExtractorTechnique, SegmentRole
from .exceptions import (
    DuplicateExtractorError,
    DuplicateProfileError,
    ExtractionEngineError,
    PipelineError,
    RegistryError,
    UnknownExtractorError,
    UnknownProfileError,
)
from .ports import (
    ClassifierPort,
    ConfidenceScorerPort,
    DocumentAdapterPort,
    ExtractorDescriptor,
    ExtractorPort,
    FrameworkMappingPort,
    KnowledgeIngestionPort,
    NormalizerPort,
    OcrPort,
    RelationshipExtractorPort,
    SegmenterPort,
)
from .profiles import (
    ConfidenceThresholds,
    ExtractionProfile,
    ExtractorRef,
    ProfileRegistry,
)
from .registry import ExtractorRegistry

__all__ = [
    # engine (pipeline coordinator)
    "ExtractionPipeline",
    "PipelinePorts",
    "PipelineOutcome",
    "StageExecutionIdFactory",
    # ports
    "DocumentAdapterPort",
    "OcrPort",
    "NormalizerPort",
    "SegmenterPort",
    "ClassifierPort",
    "ExtractorPort",
    "RelationshipExtractorPort",
    "ConfidenceScorerPort",
    "FrameworkMappingPort",
    "KnowledgeIngestionPort",
    "ExtractorDescriptor",
    # registries & profiles
    "ExtractorRegistry",
    "ProfileRegistry",
    "ExtractionProfile",
    "ExtractorRef",
    "ConfidenceThresholds",
    # artifacts
    "LayoutBlock",
    "ParsedDocument",
    "NormalizedDocument",
    "Segment",
    "SegmentTree",
    "ClassificationResult",
    "ExtractionContext",
    "CandidateSet",
    "ScoringSignals",
    "SectionPlan",
    "DocumentPlan",
    "ExtractionResult",
    "IngestionResult",
    # enums
    "ExtractorTechnique",
    "BlockKind",
    "SegmentRole",
    # exceptions
    "ExtractionEngineError",
    "PipelineError",
    "RegistryError",
    "DuplicateExtractorError",
    "UnknownExtractorError",
    "DuplicateProfileError",
    "UnknownProfileError",
]
