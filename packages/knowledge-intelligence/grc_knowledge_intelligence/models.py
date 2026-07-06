"""Value objects for the Autonomous Knowledge Engine (ADR-0025).

Deliberately independent of ``grc_persistence_web``/``grc_llm`` types — concrete adapters
translate their own records into these at the boundary (CLAUDE.md §15), which is what keeps
``gap_detection.py`` and ``engine.py`` pure functions of plain data, the same pattern
``grc_regulatory_intelligence`` established for obligations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import GapStatus, KnowledgeDomain, TrustedSourceType, VerificationStatus


@dataclass(frozen=True)
class KnowledgeQuestion:
    """One important question a GRC/compliance/legal professional needs an answer for —
    sourced from the ``/knowledge-catalog`` data files, never invented at runtime."""

    question_id: str
    question: str
    domain: KnowledgeDomain
    category: str

    def __post_init__(self) -> None:
        if not self.question_id.strip():
            raise ValueError("KnowledgeQuestion.question_id must not be empty")
        if not self.question.strip():
            raise ValueError("KnowledgeQuestion.question must not be empty")
        if not self.category.strip():
            raise ValueError("KnowledgeQuestion.category must not be empty")


@dataclass(frozen=True)
class TrustedSource:
    """A source the Knowledge Engine is allowed to research from. ``source_type`` must be one
    of ``TrustedSourceType`` — there is no way to construct a ``TrustedSource`` backed by an
    arbitrary blog or unclassified site ("Do not use random blogs" — ADR-0025)."""

    source_id: str
    name: str
    source_type: TrustedSourceType
    url: str
    jurisdiction: str

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("TrustedSource.source_id must not be empty")
        if not self.name.strip():
            raise ValueError("TrustedSource.name must not be empty")
        if not self.url.strip():
            raise ValueError("TrustedSource.url must not be empty")


@dataclass(frozen=True)
class SourceExcerpt:
    """Text already fetched from a ``TrustedSource``, ready for extraction. Fetching itself
    (crawling a regulator site, a standards body's publication library, ...) is out of scope
    for this phase — see ADR-0025's future-work note; this package only ever receives text
    that some upstream, already-trusted mechanism produced."""

    source: TrustedSource
    text: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("SourceExcerpt.text must not be empty")
        if self.fetched_at.tzinfo is None:
            raise ValueError("SourceExcerpt.fetched_at must be timezone-aware")


@dataclass(frozen=True)
class KnowledgeAnswer:
    """A candidate answer synthesized from one ``SourceExcerpt`` for one
    ``KnowledgeQuestion`` — the output of the (Tool-audited, LLM-backed) extraction step,
    before it becomes a stored ``KnowledgeItem``."""

    answer: str
    applicable_context: str
    confidence: float

    def __post_init__(self) -> None:
        if not self.answer.strip():
            raise ValueError("KnowledgeAnswer.answer must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("KnowledgeAnswer.confidence must be within [0, 1]")


@dataclass(frozen=True)
class KnowledgeItem:
    """One piece of verified-or-not GRC knowledge — never treated as absolute (ADR-0025 §6):
    ``status`` starts ``DISCOVERED`` and only a human decision moves it forward. Every
    ``KnowledgeItem`` traces to exactly one ``TrustedSource`` via ``citation``; there is no
    field here for unsourced knowledge."""

    id: str
    question_id: str
    question: str
    answer: str
    domain: KnowledgeDomain
    category: str
    applicable_context: str
    source: TrustedSource
    citation: str
    jurisdiction: str
    confidence: float
    status: VerificationStatus
    last_verified: datetime | None
    version: int

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("KnowledgeItem.id must not be empty")
        if not self.answer.strip():
            raise ValueError("KnowledgeItem.answer must not be empty")
        if not self.citation.strip():
            raise ValueError("KnowledgeItem.citation must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("KnowledgeItem.confidence must be within [0, 1]")
        if self.version < 1:
            raise ValueError("KnowledgeItem.version must be >= 1")
        if self.last_verified is not None and self.last_verified.tzinfo is None:
            raise ValueError("KnowledgeItem.last_verified must be timezone-aware")


@dataclass(frozen=True)
class GapFinding:
    """The Knowledge Gap Detector's verdict for one question: is it missing, outdated, only
    weakly answered, or already answered well enough to skip?"""

    question: KnowledgeQuestion
    status: GapStatus
    existing_item: KnowledgeItem | None
    rationale: str

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise ValueError("GapFinding.rationale must not be empty")
        if self.status is GapStatus.ANSWERED and self.existing_item is None:
            raise ValueError("GapFinding.existing_item is required when status is ANSWERED")
