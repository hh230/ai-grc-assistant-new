"""Unit tests for the pure, deterministic Knowledge Gap Detector: missing questions, an
outdated item (by status and by age), a weak-confidence item, an answered item, and a
needs-review item — plus the ``actionable_gaps`` filter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from grc_knowledge_intelligence import (
    GapStatus,
    KnowledgeDomain,
    KnowledgeItem,
    KnowledgeQuestion,
    TrustedSource,
    TrustedSourceType,
    VerificationStatus,
    actionable_gaps,
    detect_gaps,
)

_NOW = datetime(2026, 7, 6, tzinfo=timezone.utc)

_SOURCE = TrustedSource(
    source_id="sa-sama",
    name="Saudi Central Bank (SAMA)",
    source_type=TrustedSourceType.GOVERNMENT_REGULATOR,
    url="https://www.sama.gov.sa",
    jurisdiction="SA",
)


def _question(question_id: str = "vendor_management.contract_clauses") -> KnowledgeQuestion:
    return KnowledgeQuestion(
        question_id=question_id,
        question="What clauses should exist in a vendor contract?",
        domain=KnowledgeDomain.VENDOR_MANAGEMENT,
        category="contract_requirements",
    )


def _item(
    *,
    question_id: str = "vendor_management.contract_clauses",
    status: VerificationStatus = VerificationStatus.VERIFIED,
    confidence: float = 0.9,
    last_verified: datetime | None = _NOW,
) -> KnowledgeItem:
    return KnowledgeItem(
        id="item-1",
        question_id=question_id,
        question="What clauses should exist in a vendor contract?",
        answer="Vendor contracts should include data protection, audit rights, and exit clauses.",
        domain=KnowledgeDomain.VENDOR_MANAGEMENT,
        category="contract_requirements",
        applicable_context="Any vendor contract involving data processing.",
        source=_SOURCE,
        citation="sa-sama#vendor_management.contract_clauses",
        jurisdiction="SA",
        confidence=confidence,
        status=status,
        last_verified=last_verified,
        version=1,
    )


def test_missing_question_has_no_existing_item() -> None:
    findings = detect_gaps([_question()], [], now=_NOW)
    assert len(findings) == 1
    assert findings[0].status is GapStatus.MISSING
    assert findings[0].existing_item is None


def test_answered_question_with_fresh_confident_verified_item() -> None:
    findings = detect_gaps([_question()], [_item()], now=_NOW)
    assert findings[0].status is GapStatus.ANSWERED
    assert findings[0].existing_item is not None


def test_outdated_status_is_a_gap_even_if_confident_and_fresh() -> None:
    item = _item(status=VerificationStatus.OUTDATED)
    findings = detect_gaps([_question()], [item], now=_NOW)
    assert findings[0].status is GapStatus.OUTDATED


def test_needs_review_status_is_treated_as_a_gap() -> None:
    item = _item(status=VerificationStatus.NEEDS_REVIEW)
    findings = detect_gaps([_question()], [item], now=_NOW)
    assert findings[0].status is GapStatus.OUTDATED


def test_stale_by_age_is_a_gap_even_when_verified() -> None:
    item = _item(last_verified=_NOW - timedelta(days=400))
    findings = detect_gaps([_question()], [item], now=_NOW, max_age_days=365)
    assert findings[0].status is GapStatus.OUTDATED


def test_never_verified_is_a_gap() -> None:
    item = _item(last_verified=None)
    findings = detect_gaps([_question()], [item], now=_NOW)
    assert findings[0].status is GapStatus.OUTDATED


def test_weak_confidence_is_a_gap_when_otherwise_fresh() -> None:
    item = _item(confidence=0.4)
    findings = detect_gaps([_question()], [item], now=_NOW, min_confidence=0.7)
    assert findings[0].status is GapStatus.WEAK_CONFIDENCE


def test_discovered_status_is_answered_if_fresh_and_confident() -> None:
    """A freshly-discovered item (pending human verification) is not re-researched purely for
    lacking VERIFIED status — that would waste research effort on something already found."""
    item = _item(status=VerificationStatus.DISCOVERED, last_verified=_NOW)
    findings = detect_gaps([_question()], [item], now=_NOW)
    assert findings[0].status is GapStatus.ANSWERED


def test_actionable_gaps_excludes_answered_questions() -> None:
    questions = [_question("a.1"), _question("a.2")]
    items = [
        KnowledgeItem(
            id="item-answered",
            question_id="a.1",
            question="q",
            answer="a",
            domain=KnowledgeDomain.VENDOR_MANAGEMENT,
            category="c",
            applicable_context="ctx",
            source=_SOURCE,
            citation="sa-sama#a.1",
            jurisdiction="SA",
            confidence=0.9,
            status=VerificationStatus.VERIFIED,
            last_verified=_NOW,
            version=1,
        )
    ]
    findings = detect_gaps(questions, items, now=_NOW)
    gaps = actionable_gaps(findings)
    assert len(findings) == 2
    assert len(gaps) == 1
    assert gaps[0].question.question_id == "a.2"


def test_detect_gaps_requires_timezone_aware_now() -> None:
    with pytest.raises(ValueError):
        detect_gaps([_question()], [], now=datetime(2026, 7, 6))
