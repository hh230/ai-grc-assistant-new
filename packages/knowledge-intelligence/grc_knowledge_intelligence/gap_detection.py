"""The Knowledge Gap Detector — pure, deterministic, no LLM (the same design choice
ADR-0020/0021 made for Policy Hunter/Policy Analyst: CLAUDE.md §1 prefers a reproducible
comparison over a model's judgment wherever one is sufficient).

Given the question catalog and the knowledge base's *current* item per question (at most one
``KnowledgeItem`` per ``question_id`` — history, if any, is the repository's concern, not
this function's), classifies each question as ``MISSING`` (never researched), ``OUTDATED``
(explicitly marked ``OUTDATED``/``NEEDS_REVIEW``, or simply stale by age), ``WEAK_CONFIDENCE``
(answered, but under the confidence bar), or ``ANSWERED`` (nothing to do). This is what "check
existing knowledge database... detect if the question is already answered... detect outdated
answers... detect weak confidence answers" (ADR-0025 §2) means concretely.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from .enums import GapStatus, VerificationStatus
from .models import GapFinding, KnowledgeItem, KnowledgeQuestion

DEFAULT_MAX_AGE_DAYS = 365
DEFAULT_MIN_CONFIDENCE = 0.7

_STALE_STATUSES = frozenset({VerificationStatus.OUTDATED, VerificationStatus.NEEDS_REVIEW})


def _is_stale(item: KnowledgeItem, *, now: datetime, max_age_days: int) -> bool:
    if item.status in _STALE_STATUSES:
        return True
    if item.last_verified is None:
        return True
    return (now - item.last_verified) > timedelta(days=max_age_days)


def _classify(
    question: KnowledgeQuestion,
    item: KnowledgeItem | None,
    *,
    now: datetime,
    max_age_days: int,
    min_confidence: float,
) -> GapFinding:
    if item is None:
        return GapFinding(
            question=question,
            status=GapStatus.MISSING,
            existing_item=None,
            rationale="No knowledge item exists for this question.",
        )

    if item.status is VerificationStatus.OUTDATED:
        return GapFinding(
            question=question,
            status=GapStatus.OUTDATED,
            existing_item=item,
            rationale="The existing knowledge item is marked outdated.",
        )

    if item.status is VerificationStatus.NEEDS_REVIEW:
        return GapFinding(
            question=question,
            status=GapStatus.OUTDATED,
            existing_item=item,
            rationale="The existing knowledge item was flagged as needing review.",
        )

    if _is_stale(item, now=now, max_age_days=max_age_days):
        age_note = (
            "has never been verified"
            if item.last_verified is None
            else f"was last verified more than {max_age_days} days ago"
        )
        return GapFinding(
            question=question,
            status=GapStatus.OUTDATED,
            existing_item=item,
            rationale=f"The existing knowledge item {age_note}.",
        )

    if item.confidence < min_confidence:
        return GapFinding(
            question=question,
            status=GapStatus.WEAK_CONFIDENCE,
            existing_item=item,
            rationale=(
                f"The existing knowledge item's confidence ({item.confidence:.2f}) is below "
                f"the minimum ({min_confidence:.2f})."
            ),
        )

    return GapFinding(
        question=question,
        status=GapStatus.ANSWERED,
        existing_item=item,
        rationale="The existing knowledge item is current and sufficiently confident.",
    )


def detect_gaps(
    questions: Sequence[KnowledgeQuestion],
    existing_items: Sequence[KnowledgeItem],
    *,
    now: datetime,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> tuple[GapFinding, ...]:
    """Classify every question in the catalog against the knowledge base's current items.

    ``existing_items`` must contain at most one item per ``question_id`` (the current one);
    pass the repository's latest-per-question view, not a full version history.
    """
    if now.tzinfo is None:
        raise ValueError("detect_gaps(now=...) must be timezone-aware")

    by_question_id = {item.question_id: item for item in existing_items}
    return tuple(
        _classify(
            question,
            by_question_id.get(question.question_id),
            now=now,
            max_age_days=max_age_days,
            min_confidence=min_confidence,
        )
        for question in questions
    )


def actionable_gaps(findings: Sequence[GapFinding]) -> tuple[GapFinding, ...]:
    """The subset of findings that actually need research — excludes ``ANSWERED``."""
    return tuple(finding for finding in findings if finding.status is not GapStatus.ANSWERED)
