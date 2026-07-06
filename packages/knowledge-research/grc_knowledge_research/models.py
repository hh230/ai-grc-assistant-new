"""Value objects for Autonomous Knowledge Research (KI-P2).

Deliberately independent of any crawler/HTTP/LLM library — concrete adapters translate their
own results into these at the boundary (CLAUDE.md §15), the same discipline
``grc_knowledge_intelligence.models`` already holds itself to. Reuses
``grc_knowledge_intelligence``'s own ``TrustedSource``/``KnowledgeQuestion``/``SourceExcerpt``/
``KnowledgeItem`` rather than redefining sibling shapes — this package plans and fetches
*for* those models, it does not compete with them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from grc_knowledge_intelligence import (
    KnowledgeDomain,
    KnowledgeItem,
    KnowledgeQuestion,
    TrustedSource,
)

from .enums import AttemptOutcome, ResearchStatus


@dataclass(frozen=True)
class DiscoveredDocumentRef:
    """One candidate document a research crawler's discovery step found at a trusted source,
    before its content is fetched. Generic — unlike
    ``grc_regulatory_intelligence.DiscoveredDocumentRef``, this type carries no assumption
    that the source is a regulator."""

    url: str
    title: str | None = None

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("DiscoveredDocumentRef.url must not be empty")


@dataclass(frozen=True)
class CatalogedSource:
    """One ``TrustedSource`` as it appears in the curated ``/trusted-sources`` directory,
    tagged with which ``KnowledgeDomain``s it is worth checking for. The tagging is what lets
    ``planning.build_research_plan`` decide *where* trustworthy information may exist without
    ever guessing at an untyped, uncurated site."""

    source: TrustedSource
    domains: tuple[KnowledgeDomain, ...]

    def __post_init__(self) -> None:
        if not self.domains:
            raise ValueError("CatalogedSource.domains must not be empty")


@dataclass(frozen=True)
class ResearchStep:
    """One probe in a research plan: check this source, at this priority rank (lower is
    checked first)."""

    source: CatalogedSource
    rank: int

    def __post_init__(self) -> None:
        if self.rank < 0:
            raise ValueError("ResearchStep.rank must be >= 0")


@dataclass(frozen=True)
class ResearchPlan:
    """The ordered list of trusted sources worth checking for one question — deterministic,
    inspectable *before* any network I/O happens, so "what will be researched, and in what
    order" is itself auditable, not implicit in a crawl's side effects."""

    question: KnowledgeQuestion
    steps: tuple[ResearchStep, ...]


@dataclass(frozen=True)
class ResearchAttempt:
    """One recorded probe against one candidate document: what source, what document (if
    discovery got that far), what happened, and why. The full sequence of attempts is the
    traceability trail behind a ``ResearchResult`` — including the sources that were checked
    and rejected, not only the one that ultimately grounded an answer."""

    source: TrustedSource
    ref: DiscoveredDocumentRef | None
    outcome: AttemptOutcome
    confidence: float | None
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("ResearchAttempt.detail must not be empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("ResearchAttempt.confidence must be within [0, 1]")


@dataclass(frozen=True)
class ResearchResult:
    """The outcome of researching one question: the best grounded ``KnowledgeItem`` found (if
    any), and the full attempt trail that produced it — the shape KI-P1's
    ``KnowledgeItemRepository.upsert`` expects to persist, plus everything an auditor needs to
    reconstruct how that answer (or the absence of one) was reached.

    ``version_hash`` is ``compute_version_hash(question, excerpt)`` for the excerpt that
    grounded ``item`` — computed once, at the moment the winning excerpt is still in hand,
    since neither ``KnowledgeItem`` nor this result otherwise retains the raw excerpt text a
    storage layer would need to recompute it later."""

    question: KnowledgeQuestion
    status: ResearchStatus
    item: KnowledgeItem | None
    version_hash: str | None
    attempts: tuple[ResearchAttempt, ...]
    researched_at: datetime

    def __post_init__(self) -> None:
        if self.status is ResearchStatus.FOUND and (self.item is None or self.version_hash is None):
            raise ValueError(
                "ResearchResult.item and .version_hash are required when status is FOUND"
            )
        if self.status is ResearchStatus.INSUFFICIENT_EVIDENCE and (
            self.item is not None or self.version_hash is not None
        ):
            raise ValueError(
                "ResearchResult.item and .version_hash must be None when status is "
                "INSUFFICIENT_EVIDENCE"
            )
        if self.researched_at.tzinfo is None:
            raise ValueError("ResearchResult.researched_at must be timezone-aware")
