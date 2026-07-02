"""Composition helpers: assemble the rule-based adapters into a runnable engine.

These build the default extractor registry, the default profiles (data), the port bundle, and a
ready ``ExtractionPipeline``. This is the engine's composition seam for the rule-based reference
configuration — adding a regulator or document type is a new profile, not an engine change
(CLAUDE.md §13).
"""
from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from grc_domain.knowledge import DocumentType
from grc_domain.shared.identifiers import StageExecutionId
from grc_extraction import (
    ConfidenceThresholds,
    ExtractionPipeline,
    ExtractionProfile,
    ExtractorRef,
    ExtractorRegistry,
    KnowledgeIngestionPort,
    PipelinePorts,
    ProfileRegistry,
    StageExecutionIdFactory,
)

from .classification import KeywordClassifier
from .documents import InMemoryTextDocumentAdapter
from .extraction import RuleBasedNormativeExtractor
from .ingestion import InMemoryKnowledgeIngestion
from .normalization import WhitespaceNormalizer
from .scoring import HeuristicConfidenceScorer
from .segmentation import HeadingSegmenter

_DEFAULT_PROFILE_TYPES: tuple[DocumentType, ...] = (
    DocumentType.STANDARD,
    DocumentType.LAW,
    DocumentType.EXECUTIVE_REGULATION,
    DocumentType.POLICY,
)


def default_extractor_registry() -> ExtractorRegistry:
    registry = ExtractorRegistry()
    registry.register(RuleBasedNormativeExtractor())
    return registry


def default_profile(document_type: DocumentType = DocumentType.STANDARD) -> ExtractionProfile:
    return ExtractionProfile(
        document_type=document_type,
        version="1.0.0",
        grammar_ref="grammar:headings.v1",
        extractor_refs=(ExtractorRef(RuleBasedNormativeExtractor.NAME),),
        thresholds=ConfidenceThresholds(auto_accept_at=0.75, review_below=0.75, discard_below=0.2),
        default_language="en",
    )


def default_profile_registry() -> ProfileRegistry:
    registry = ProfileRegistry()
    for document_type in _DEFAULT_PROFILE_TYPES:
        registry.register(default_profile(document_type))
    return registry


def uuid_stage_execution_ids() -> StageExecutionIdFactory:
    def _next() -> StageExecutionId:
        return StageExecutionId(f"se-{uuid4().hex}")

    return _next


def build_default_ports(
    corpus: Mapping[str, str], *, ingestion: KnowledgeIngestionPort | None = None
) -> PipelinePorts:
    return PipelinePorts(
        document_adapter=InMemoryTextDocumentAdapter(corpus),
        normalizer=WhitespaceNormalizer(),
        segmenter=HeadingSegmenter(),
        classifier=KeywordClassifier(),
        extractors=default_extractor_registry(),
        scorer=HeuristicConfidenceScorer(),
        ingestion=ingestion if ingestion is not None else InMemoryKnowledgeIngestion(),
    )


def build_pipeline(
    corpus: Mapping[str, str],
    *,
    ingestion: KnowledgeIngestionPort | None = None,
    new_stage_execution_id: StageExecutionIdFactory | None = None,
) -> ExtractionPipeline:
    ports = build_default_ports(corpus, ingestion=ingestion)
    return ExtractionPipeline(
        ports,
        new_stage_execution_id=(
            new_stage_execution_id
            if new_stage_execution_id is not None
            else uuid_stage_execution_ids()
        ),
    )
