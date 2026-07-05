"""Unit tests for RegulatoryDocumentInput's anti-corruption translation and pure change
detection (PI-P2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from grc_regulatory_intelligence import (
    DiscoveredDocumentRef,
    DocumentChangeType,
    DocumentContentType,
    RegulatoryDocumentInput,
    detect_change,
)


def _document_input(raw_text: str = "1. Entities shall encrypt data.") -> RegulatoryDocumentInput:
    return RegulatoryDocumentInput(
        source_id="sa-sama",
        url="https://www.sama.gov.sa/regulations/1",
        raw_text=raw_text,
        content_type=DocumentContentType.HTML,
        discovered_at=datetime(2026, 7, 6, tzinfo=timezone.utc),
        title="Circular 1",
    )


def test_to_raw_regulatory_document_computes_a_stable_content_hash() -> None:
    document_input = _document_input()

    raw = document_input.to_raw_regulatory_document()

    assert raw.source_id == "sa-sama"
    assert raw.url == document_input.url
    assert raw.raw_text == document_input.raw_text
    assert len(raw.content_hash) == 64  # sha256 hex digest
    # Same text -> same hash, independent of other metadata (deterministic).
    assert _document_input().to_raw_regulatory_document().content_hash == raw.content_hash


def test_to_raw_regulatory_document_hash_changes_with_text() -> None:
    first = _document_input("1. Entities shall encrypt data.").to_raw_regulatory_document()
    second = _document_input(
        "1. Entities shall encrypt data AND log access."
    ).to_raw_regulatory_document()
    assert first.content_hash != second.content_hash


def test_document_input_requires_timezone_aware_discovered_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        RegulatoryDocumentInput(
            source_id="sa-sama",
            url="https://www.sama.gov.sa",
            raw_text="text",
            content_type=DocumentContentType.TEXT,
            discovered_at=datetime(2026, 7, 6),  # naive
        )


def test_discovered_document_ref_rejects_empty_url() -> None:
    with pytest.raises(ValueError, match="url"):
        DiscoveredDocumentRef(url="  ")


def test_detect_change_new_when_no_previous_hash() -> None:
    assert (
        detect_change(previous_content_hash=None, current_content_hash="abc")
        == DocumentChangeType.NEW
    )


def test_detect_change_unchanged_when_hash_matches() -> None:
    assert (
        detect_change(previous_content_hash="abc", current_content_hash="abc")
        == DocumentChangeType.UNCHANGED
    )


def test_detect_change_updated_when_hash_differs() -> None:
    assert (
        detect_change(previous_content_hash="abc", current_content_hash="def")
        == DocumentChangeType.UPDATED
    )


def test_detect_change_removed_when_unavailable_regardless_of_hash() -> None:
    assert (
        detect_change(
            previous_content_hash="abc", current_content_hash="abc", currently_available=False
        )
        == DocumentChangeType.REMOVED
    )
    assert (
        detect_change(
            previous_content_hash=None, current_content_hash="abc", currently_available=False
        )
        == DocumentChangeType.REMOVED
    )
