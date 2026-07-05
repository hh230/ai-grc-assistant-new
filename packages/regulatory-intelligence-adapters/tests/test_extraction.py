"""Unit tests for the deterministic, rule-based obligation extractor."""

from __future__ import annotations

from datetime import datetime, timezone

from grc_regulatory_intelligence import RawRegulatoryDocument
from grc_regulatory_intelligence_adapters import RuleBasedObligationExtractor


def _document(raw_text: str) -> RawRegulatoryDocument:
    return RawRegulatoryDocument(
        source_id="src",
        url="https://example.gov",
        fetched_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
        content_hash="hash",
        raw_text=raw_text,
    )


async def test_splits_numbered_clauses_with_accurate_offsets() -> None:
    raw_text = (
        "1. Entities shall encrypt data at rest and in transit.\n"
        "2. Entities shall log every access to sensitive data."
    )
    document = _document(raw_text)
    extractor = RuleBasedObligationExtractor()

    candidates = await extractor.extract(document)

    assert len(candidates) == 2
    for candidate in candidates:
        # Offsets must point exactly at the stored obligation text.
        assert raw_text[candidate.source_char_start : candidate.source_char_end] == (
            candidate.obligation_text
        )
    assert candidates[0].obligation_text.startswith("1. Entities shall encrypt")
    assert candidates[1].obligation_text.startswith("2. Entities shall log")


async def test_falls_back_to_sentence_boundaries_without_numbered_clauses() -> None:
    raw_text = "Entities shall encrypt data at rest. Entities shall log every access attempt."
    document = _document(raw_text)
    extractor = RuleBasedObligationExtractor()

    candidates = await extractor.extract(document)

    assert len(candidates) == 2
    assert candidates[0].obligation_text == "Entities shall encrypt data at rest."
    assert candidates[1].obligation_text == "Entities shall log every access attempt."


async def test_filters_out_noise_shorter_than_the_minimum_obligation_length() -> None:
    raw_text = "1. No.\n2. Entities shall retain audit logs for at least twelve months."
    document = _document(raw_text)
    extractor = RuleBasedObligationExtractor()

    candidates = await extractor.extract(document)

    assert len(candidates) == 1
    assert candidates[0].obligation_text.startswith("2. Entities shall retain audit logs")


async def test_single_clause_document_returns_one_candidate() -> None:
    raw_text = "Entities shall maintain an incident response plan reviewed annually."
    document = _document(raw_text)
    extractor = RuleBasedObligationExtractor()

    candidates = await extractor.extract(document)

    assert len(candidates) == 1
    assert candidates[0].obligation_text == raw_text
