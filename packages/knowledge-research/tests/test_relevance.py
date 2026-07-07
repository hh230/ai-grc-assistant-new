"""Unit tests for the deterministic word-overlap relevance scorer."""

from __future__ import annotations

from grc_knowledge_intelligence import KnowledgeDomain, KnowledgeQuestion
from grc_knowledge_research import DiscoveredDocumentRef, rank_refs, score_relevance

_QUESTION = KnowledgeQuestion(
    question_id="vendor_management.contract_clauses",
    question="What clauses should exist in a vendor contract?",
    domain=KnowledgeDomain.VENDOR_MANAGEMENT,
    category="contract_requirements",
)


def test_score_relevance_is_one_when_every_question_word_appears() -> None:
    assert score_relevance("vendor contract clauses", "vendor contract clauses audit rights") == 1.0


def test_score_relevance_is_zero_for_no_overlap() -> None:
    assert score_relevance("vendor contract clauses", "unrelated topic entirely") == 0.0


def test_score_relevance_is_zero_for_empty_text_on_either_side() -> None:
    assert score_relevance("", "vendor contract clauses") == 0.0
    assert score_relevance("vendor contract clauses", "") == 0.0


def test_rank_refs_orders_most_relevant_title_first() -> None:
    off_topic = DiscoveredDocumentRef(url="https://example.gov/holidays", title="Public holidays")
    on_topic = DiscoveredDocumentRef(
        url="https://example.gov/vendor-contracts", title="Vendor contract requirements"
    )

    ranked = rank_refs(_QUESTION, (off_topic, on_topic))

    assert ranked == (on_topic, off_topic)


def test_rank_refs_falls_back_to_url_when_title_is_missing() -> None:
    ref = DiscoveredDocumentRef(url="https://example.gov/vendor-contract-clauses")

    ranked = rank_refs(_QUESTION, (ref,))

    assert ranked == (ref,)


def test_rank_refs_still_uses_the_url_when_the_title_is_in_another_language() -> None:
    """A bilingual regulator site's real nav titles are often not in the question's
    language (e.g. Arabic) — ``_WORD_RE`` only recognizes ASCII words, so a non-English
    title alone tokenizes to nothing. The URL slug is routinely still English/transliterated
    and must not be discarded just because a (irrelevant, untranslatable) title exists."""
    off_topic = DiscoveredDocumentRef(url="https://example.gov/ar/news/", title="الأخبار")
    on_topic = DiscoveredDocumentRef(
        url="https://example.gov/ar/vendor-contract-clauses/", title="متطلبات العقود"
    )

    ranked = rank_refs(_QUESTION, (off_topic, on_topic))

    assert ranked == (on_topic, off_topic)
