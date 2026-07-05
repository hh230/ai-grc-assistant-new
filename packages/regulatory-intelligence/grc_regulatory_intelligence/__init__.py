"""grc_regulatory_intelligence — the pure Regulatory Intelligence engine (Policy Intelligence
PI-P1: obligation split/classify pipeline; PI-P2: source registry, crawler discovery/change
detection contracts). See README.md for the flow this package sits in.
"""

from __future__ import annotations

from .artifacts import (
    ClassifiedObligation,
    ObligationCandidate,
    ObligationClassification,
    RawRegulatoryDocument,
    RegulatoryIntelligenceResult,
    compute_version_hash,
)
from .change_detection import DocumentChangeType, detect_change
from .documents import DiscoveredDocumentRef, DocumentContentType, RegulatoryDocumentInput
from .engine import RegulatoryIntelligenceEngine
from .enums import ClassificationStatus, ControlDomain, ObligationType, Severity
from .exceptions import ObligationClassificationError, RegulatoryIntelligenceError
from .ports import CrawlerPort, ObligationClassifierPort, ObligationExtractorPort
from .source_config import build_registry, load_source, load_source_file
from .sources import PollingFrequency, RegulatorySource, RegulatorySourceRegistry, SourceType

__all__ = [
    "ClassificationStatus",
    "ClassifiedObligation",
    "ControlDomain",
    "CrawlerPort",
    "DiscoveredDocumentRef",
    "DocumentChangeType",
    "DocumentContentType",
    "ObligationCandidate",
    "ObligationClassification",
    "ObligationClassificationError",
    "ObligationClassifierPort",
    "ObligationExtractorPort",
    "ObligationType",
    "PollingFrequency",
    "RawRegulatoryDocument",
    "RegulatoryDocumentInput",
    "RegulatoryIntelligenceEngine",
    "RegulatoryIntelligenceError",
    "RegulatoryIntelligenceResult",
    "RegulatorySource",
    "RegulatorySourceRegistry",
    "Severity",
    "SourceType",
    "build_registry",
    "compute_version_hash",
    "detect_change",
    "load_source",
    "load_source_file",
]
