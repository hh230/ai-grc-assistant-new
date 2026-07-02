"""grc_extraction_adapters — concrete rule-based adapters for the Knowledge Extraction Engine.

These implement the ``grc_extraction`` ports (document/normalize/segment/classify/extract/score and
a reference ingestion) using deterministic rules and standard-library text processing only — no
OCR, NLP library, LLM, or database. They make the engine runnable and testable end to end, and
serve as the contract reference for richer (library-/AI-backed) adapters added later behind the
same ports. This is an **outer infrastructure** package: it depends on ``grc_extraction`` and
``grc_domain`` and nothing depends on it.
"""
from __future__ import annotations

from .classification import KeywordClassifier
from .composition import (
    build_default_ports,
    build_pipeline,
    default_extractor_registry,
    default_profile,
    default_profile_registry,
    uuid_stage_execution_ids,
)
from .documents import InMemoryTextDocumentAdapter
from .exceptions import AdapterError, DocumentNotAvailableError
from .extraction import RuleBasedNormativeExtractor
from .ingestion import InMemoryKnowledgeIngestion
from .normalization import WhitespaceNormalizer
from .scoring import HeuristicConfidenceScorer
from .segmentation import HeadingSegmenter

__all__ = [
    # adapters
    "InMemoryTextDocumentAdapter",
    "WhitespaceNormalizer",
    "HeadingSegmenter",
    "KeywordClassifier",
    "RuleBasedNormativeExtractor",
    "HeuristicConfidenceScorer",
    "InMemoryKnowledgeIngestion",
    # composition
    "build_default_ports",
    "build_pipeline",
    "default_extractor_registry",
    "default_profile",
    "default_profile_registry",
    "uuid_stage_execution_ids",
    # exceptions
    "AdapterError",
    "DocumentNotAvailableError",
]
