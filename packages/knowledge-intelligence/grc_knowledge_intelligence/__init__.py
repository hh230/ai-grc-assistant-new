"""grc_knowledge_intelligence — the Autonomous Knowledge Engine's pure pipeline (KI-P1,
ADR-0025): a Knowledge Question Generator (catalog-driven), a Knowledge Gap Detector (pure,
deterministic), and a Knowledge Discovery engine that coordinates trusted-source-grounded
extraction via an injected port. See README.md.
"""

from __future__ import annotations

from .engine import KnowledgeDiscoveryEngine, compute_version_hash
from .enums import GapStatus, KnowledgeDomain, TrustedSourceType, VerificationStatus
from .exceptions import KnowledgeEngineError, KnowledgeExtractionError
from .gap_detection import (
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_MIN_CONFIDENCE,
    actionable_gaps,
    detect_gaps,
)
from .models import (
    GapFinding,
    KnowledgeAnswer,
    KnowledgeItem,
    KnowledgeQuestion,
    SourceExcerpt,
    TrustedSource,
)
from .ports import KnowledgeExtractorPort
from .question_catalog import build_catalog, load_questions, load_questions_file

__all__ = [
    "DEFAULT_MAX_AGE_DAYS",
    "DEFAULT_MIN_CONFIDENCE",
    "GapFinding",
    "GapStatus",
    "KnowledgeAnswer",
    "KnowledgeDiscoveryEngine",
    "KnowledgeDomain",
    "KnowledgeEngineError",
    "KnowledgeExtractionError",
    "KnowledgeExtractorPort",
    "KnowledgeItem",
    "KnowledgeQuestion",
    "SourceExcerpt",
    "TrustedSource",
    "TrustedSourceType",
    "VerificationStatus",
    "actionable_gaps",
    "build_catalog",
    "compute_version_hash",
    "detect_gaps",
    "load_questions",
    "load_questions_file",
]
