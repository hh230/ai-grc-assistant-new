"""grc_knowledge_research — Autonomous Knowledge Research (KI-P2): the pure pipeline that
turns a Knowledge Gap Detector finding into a research plan over a curated trusted-source
catalog, and coordinates grounded discovery across it via the (unmodified)
``grc_knowledge_intelligence.KnowledgeDiscoveryEngine``. See README.md.
"""

from __future__ import annotations

from .coordinator import (
    DEFAULT_EARLY_STOP_CONFIDENCE,
    DEFAULT_MAX_DOCUMENTS_PER_SOURCE,
    DEFAULT_MAX_SOURCES,
    ResearchCoordinator,
)
from .enums import AttemptOutcome, ResearchStatus
from .models import (
    CatalogedSource,
    DiscoveredDocumentRef,
    ResearchAttempt,
    ResearchPlan,
    ResearchResult,
    ResearchStep,
)
from .planning import build_research_plan
from .ports import ResearchCrawlerPort
from .relevance import rank_refs, score_relevance

__all__ = [
    "DEFAULT_EARLY_STOP_CONFIDENCE",
    "DEFAULT_MAX_DOCUMENTS_PER_SOURCE",
    "DEFAULT_MAX_SOURCES",
    "AttemptOutcome",
    "CatalogedSource",
    "DiscoveredDocumentRef",
    "ResearchAttempt",
    "ResearchCoordinator",
    "ResearchCrawlerPort",
    "ResearchPlan",
    "ResearchResult",
    "ResearchStatus",
    "ResearchStep",
    "build_research_plan",
    "rank_refs",
    "score_relevance",
]
