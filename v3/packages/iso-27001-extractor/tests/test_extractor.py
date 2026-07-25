"""Tests for the ISO 27001 extractor. DoD = PROOF of three new properties:
  1. Native ≠ Canonical (native Theme → canonical Category),
  2. Storage ≠ Egress (Licensed: full text stored + egress_restricted),
  3. the Extractor DESCRIBES reality (a formal note for the partial rendition).

The fixture uses SYNTHETIC control text — ISO is Licensed, so no real ISO text is
embedded; the real document is exercised only by the (skippable) integration test, which
asserts counts, never content.
"""
from __future__ import annotations

import glob
from dataclasses import replace

import pytest

from knowledge_extraction.port import KnowledgeExtractionPort, ResolvedSource, SourceFacets
from iso_27001_extractor import IsoKnowledgeExtractor, parse_iso_annex

# Synthetic — NOT real ISO text. Only the structural FORMAT matters.
FIXTURE = (
    "Organizational controls \n"
    "5.1 Placeholder organizational control one \n"
    "5.2 Placeholder organizational control two \n"
    "People controls \n"
    "6.1 Placeholder people control \n"
    "Physical controls \n"
    "7.1 Placeholder physical control \n"
    "Technological controls \n"
    "8.1 Placeholder technological control one \n"
    "8.2 Placeholder technological control two \n"
)


def _iso_source() -> ResolvedSource:
    return ResolvedSource(
        source_id="ISO-27001", version="2022", language="EN", variant="Official",
        physical_path="/opaque/iso.pdf", sha256="x",
        facets=SourceFacets(
            authority="Normative", license="Licensed", stability="Stable",
            genre="International-Standard",
            grc_domains=("ISEC", "CYB", "GOV", "RSK"),
        ),
    )


def _artifact():
    return IsoKnowledgeExtractor().extract_from_text(_iso_source(), FIXTURE)


def test_parse_is_deterministic() -> None:
    assert parse_iso_annex(FIXTURE) == parse_iso_annex(FIXTURE)


def test_conforms_to_port() -> None:
    extractor = IsoKnowledgeExtractor()
    assert isinstance(extractor, KnowledgeExtractionPort)
    assert extractor.accepts(_iso_source()) is True
    assert extractor.accepts(replace(_iso_source(), source_id="NIST-CSF")) is False


# --- Property 1: Native ≠ Canonical ----------------------------------------
def test_native_differs_from_canonical() -> None:
    art = _artifact()
    themes = [e for e in art.entities if e.type == "Category"]
    controls = [e for e in art.entities if e.type == "Control"]
    assert len(themes) == 4 and len(controls) == 6
    # a Theme is stored as canonical Category but retains its native node name
    assert all(t.native_node_type == "Theme" and t.type == "Category" for t in themes)
    assert all(c.native_node_type == "Control" and c.type == "Control" for c in controls)
    # Annex ids are disambiguated with the `A.` prefix
    assert {t.entity_id for t in themes} == {
        "ISO-27001@2022::A.5", "ISO-27001@2022::A.6",
        "ISO-27001@2022::A.7", "ISO-27001@2022::A.8",
    }
    assert "ISO-27001@2022::A.5.1" in {c.entity_id for c in controls}


# --- Property 2: Storage ≠ Egress ------------------------------------------
def test_storage_not_egress() -> None:
    art = _artifact()
    for e in art.entities:
        assert e.license == "Licensed"
        assert e.egress_restricted is True          # marker set…
        assert e.description != ""                    # …but full content is STORED


# --- Property 3: the extractor describes reality (partial rendition) --------
def test_records_formal_partial_clause_note() -> None:
    art = _artifact()
    assert art.summary.warnings == 1
    note = art.warnings[0]
    assert note.subject.startswith("Management Clauses")
    assert note.status == "Partial"
    assert "rendition" in note.reason.lower()
    assert "acquire" in note.recommended_action.lower()
    # It did NOT fail and did NOT invent clauses:
    assert all(e.type in {"Category", "Control"} for e in art.entities)


# --- DoD: contract, reproducibility, no invention --------------------------
def test_artifact_satisfies_contract_and_hierarchy() -> None:
    art = _artifact()
    assert art.summary.counts_by_type == {"Category": 4, "Control": 6}
    assert art.summary.entities == 10
    assert art.summary.structural_relationships == 6  # 6 controls → their themes
    ids = {e.entity_id for e in art.entities}
    for e in art.entities:
        if e.parent is not None:
            assert e.parent in ids


def test_reproducible_and_no_invention() -> None:
    a1, a2 = _artifact(), _artifact()
    assert a1.identity.content_hash == a2.identity.content_hash
    for e in a1.entities:
        assert e.number is not None and e.number.removeprefix("A.") in FIXTURE


# --- Integration: the real, Licensed corpus PDF (skips where absent) --------
def _real_pdf() -> str | None:
    base = "/Users/mohamedalsayyar/Documents/قاعدة بيانات مشروع Ai GRC/ISO/ISO 27001"
    hits = glob.glob(base + "/*.pdf")
    return hits[0] if hits else None


@pytest.mark.skipif(_real_pdf() is None, reason="ISO 27001 corpus PDF not present")
def test_real_iso_annex_counts_no_content_asserted() -> None:
    try:
        import fitz  # noqa: F401
    except ImportError:
        pytest.skip("fitz not available")
    source = replace(_iso_source(), physical_path=_real_pdf() or "")
    art = IsoKnowledgeExtractor().extract(source)
    # Counts only — never assert Licensed content.
    assert art.summary.counts_by_type == {"Category": 4, "Control": 93}
    assert art.summary.warnings == 1  # the Management-Clauses partial note
    assert all(e.egress_restricted for e in art.entities)
    assert art.identity.content_hash == IsoKnowledgeExtractor().extract(source).identity.content_hash
