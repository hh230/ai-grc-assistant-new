"""grc_regulatory_intelligence_adapters — concrete adapters for the Regulatory Intelligence
engine (connectors, rule-based extraction, LLM classification). See README.md.
"""

from __future__ import annotations

from .classification import (
    TOOL_NAME,
    TOOL_VERSION,
    ClassifyObligationInput,
    ClassifyObligationOutput,
    ClassifyRegulatoryObligationTool,
    LlmObligationClassifier,
)
from .connectors import (
    FetchedRegulatoryDocument,
    HttpRegulatoryConnector,
    RegulatoryConnectorPort,
    StaticRegulatoryConnector,
)
from .exceptions import ClassificationRejectedError, ConnectorFetchError
from .extraction import RuleBasedObligationExtractor
from .prompts import CLASSIFY_REGULATORY_OBLIGATION_VERSION

__all__ = [
    "CLASSIFY_REGULATORY_OBLIGATION_VERSION",
    "TOOL_NAME",
    "TOOL_VERSION",
    "ClassificationRejectedError",
    "ClassifyObligationInput",
    "ClassifyObligationOutput",
    "ClassifyRegulatoryObligationTool",
    "ConnectorFetchError",
    "FetchedRegulatoryDocument",
    "HttpRegulatoryConnector",
    "LlmObligationClassifier",
    "RegulatoryConnectorPort",
    "RuleBasedObligationExtractor",
    "StaticRegulatoryConnector",
]
