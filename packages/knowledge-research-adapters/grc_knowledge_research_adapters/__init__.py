"""grc_knowledge_research_adapters — Autonomous Knowledge Research (KI-P2): the concrete,
polite HTTP crawler, the curated trusted-source catalog loader, and the
``KnowledgeGapResearchRunner`` that ties gap detection, research, and storage together. See
README.md.
"""

from __future__ import annotations

from .crawler import DEFAULT_MAX_EXCERPT_CHARS, DEFAULT_USER_AGENT, HttpResearchCrawler
from .runner import (
    GapResearchOutcome,
    KnowledgeGapResearchRunner,
    KnowledgeItemStore,
    StoredKnowledgeItem,
)
from .trusted_source_catalog import (
    build_trusted_source_catalog,
    load_cataloged_source,
    load_cataloged_source_file,
)

__all__ = [
    "DEFAULT_MAX_EXCERPT_CHARS",
    "DEFAULT_USER_AGENT",
    "GapResearchOutcome",
    "HttpResearchCrawler",
    "KnowledgeGapResearchRunner",
    "KnowledgeItemStore",
    "StoredKnowledgeItem",
    "build_trusted_source_catalog",
    "load_cataloged_source",
    "load_cataloged_source_file",
]
