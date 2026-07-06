"""Unit tests for ``KnowledgeDiscoveryEngine``: a successful discovery, a rejected extraction
(fails safe — returns ``None``, never guesses), and the deterministic version hash."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from grc_knowledge_intelligence import (
    KnowledgeAnswer,
    KnowledgeDiscoveryEngine,
    KnowledgeDomain,
    KnowledgeExtractionError,
    KnowledgeExtractorPort,
    KnowledgeQuestion,
    SourceExcerpt,
    TrustedSource,
    TrustedSourceType,
    VerificationStatus,
    compute_version_hash,
)

_SOURCE = TrustedSource(
    source_id="sa-sama",
    name="Saudi Central Bank (SAMA)",
    source_type=TrustedSourceType.GOVERNMENT_REGULATOR,
    url="https://www.sama.gov.sa",
    jurisdiction="SA",
)

_QUESTION = KnowledgeQuestion(
    question_id="vendor_management.contract_clauses",
    question="What clauses should exist in a vendor contract?",
    domain=KnowledgeDomain.VENDOR_MANAGEMENT,
    category="contract_requirements",
)

_EXCERPT = SourceExcerpt(
    source=_SOURCE,
    text="Vendor contracts must include audit rights, data protection clauses, and exit terms.",
    fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
)


class FakeExtractor(KnowledgeExtractorPort):
    def __init__(self, *, answer: KnowledgeAnswer | None = None, raises: bool = False) -> None:
        self._answer = answer
        self._raises = raises

    async def extract(self, question: KnowledgeQuestion, excerpt: SourceExcerpt) -> KnowledgeAnswer:
        if self._raises:
            raise KnowledgeExtractionError("could not ground an answer in this excerpt")
        assert self._answer is not None
        return self._answer


async def test_discover_returns_a_discovered_item_grounded_in_the_excerpt() -> None:
    answer = KnowledgeAnswer(
        answer="Vendor contracts should include audit rights, data protection, and exit clauses.",
        applicable_context="Any vendor contract involving data processing.",
        confidence=0.85,
    )
    engine = KnowledgeDiscoveryEngine(
        extractor=FakeExtractor(answer=answer), id_factory=lambda: "item-1"
    )

    item = await engine.discover(_QUESTION, _EXCERPT)

    assert item is not None
    assert item.id == "item-1"
    assert item.question_id == "vendor_management.contract_clauses"
    assert item.answer == answer.answer
    assert item.confidence == 0.85
    assert item.status is VerificationStatus.DISCOVERED
    assert item.last_verified is None
    assert item.version == 1
    assert item.citation == "sa-sama#vendor_management.contract_clauses"
    assert item.source == _SOURCE


async def test_discover_returns_none_when_extraction_fails() -> None:
    engine = KnowledgeDiscoveryEngine(extractor=FakeExtractor(raises=True))

    item = await engine.discover(_QUESTION, _EXCERPT)

    assert item is None


def test_version_hash_is_deterministic_and_content_derived() -> None:
    first = compute_version_hash(_QUESTION, _EXCERPT)
    second = compute_version_hash(_QUESTION, _EXCERPT)
    assert first == second

    different_excerpt = SourceExcerpt(
        source=_SOURCE, text="Different text entirely.", fetched_at=_EXCERPT.fetched_at
    )
    assert compute_version_hash(_QUESTION, different_excerpt) != first


async def test_discover_is_independent_across_calls_with_fresh_ids() -> None:
    answer = KnowledgeAnswer(answer="Answer text.", applicable_context="ctx", confidence=0.8)
    engine = KnowledgeDiscoveryEngine(extractor=FakeExtractor(answer=answer))

    first = await engine.discover(_QUESTION, _EXCERPT)
    second = await engine.discover(_QUESTION, _EXCERPT)

    assert first is not None and second is not None
    assert first.id != second.id  # default id_factory generates a fresh uuid4 each call


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_knowledge_answer_rejects_out_of_range_confidence(confidence: float) -> None:
    with pytest.raises(ValueError):
        KnowledgeAnswer(answer="x", applicable_context="ctx", confidence=confidence)
