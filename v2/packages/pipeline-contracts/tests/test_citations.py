"""Citation behaviour — the canonical formatting, validity, identity, and derivation rules.

These are the rules the whole platform's grounding claim rests on, so they are tested here,
at their one definition, rather than only through whichever engine happens to call them.
"""

from __future__ import annotations

import json
from dataclasses import replace

from pipeline_contracts import (
    Citation,
    build_citation,
    citation_is_complete,
    citation_key,
    clause_key,
    format_citation,
    is_citable,
    missing_facets,
    respan,
)

from tests.conftest import make_chunk, make_citation


# ── formatting ────────────────────────────────────────────────────────────────
def test_format_uses_document_then_code_and_title_then_page():
    assert format_citation(make_chunk()) == "pdpl.pdf — 5-1 Data Processing — p. 3"


def test_format_collapses_a_single_page_span_and_expands_a_real_one():
    assert format_citation(make_chunk(page_start=3, page_end=3)).endswith("p. 3")
    assert format_citation(make_chunk(page_start=3, page_end=5)).endswith("pp. 3–5")
    # an open-ended span reads as its start page
    assert format_citation(make_chunk(page_start=3, page_end=None)).endswith("p. 3")


def test_format_falls_back_to_the_heading_path_when_there_is_no_code():
    formatted = format_citation(make_chunk(code=None))
    assert formatted == "pdpl.pdf — Chapter 2 › Article 5 Data Processing — p. 3"


def test_format_uses_the_bare_title_when_there_is_no_locator_at_all():
    formatted = format_citation(make_chunk(code=None, heading_path=()))
    assert formatted == "pdpl.pdf — Data Processing — p. 3"


def test_format_omits_every_absent_facet():
    assert format_citation(
        make_chunk(code=None, title=None, heading_path=(), page_start=None, page_end=None)
    ) == "pdpl.pdf"


def test_a_chunk_and_the_citation_built_from_it_format_identically():
    """The reason one formatter serves both shapes: a citation must never render
    differently from the chunk it came from."""
    chunk = make_chunk(page_start=7, page_end=9)
    assert format_citation(build_citation(chunk)) == format_citation(chunk)


# ── construction ──────────────────────────────────────────────────────────────
def test_build_citation_carries_every_facet_across_and_formats_it():
    citation = build_citation(make_chunk())
    assert citation.source_filename == "pdpl.pdf"
    assert citation.category == "laws"
    assert citation.document_profile == "law"
    assert citation.structure_profile == "regulation_article"
    assert citation.code == "5-1"
    assert citation.title == "Data Processing"
    assert citation.heading_path == ("Chapter 2", "Article 5")
    assert citation.page_start == 3 and citation.page_end == 3
    assert citation.formatted == "pdpl.pdf — 5-1 Data Processing — p. 3"


def test_citation_is_frozen_and_serializes_to_plain_json():
    data = make_citation().to_dict()
    assert data["heading_path"] == ["Chapter 2", "Article 5"]  # tuple → list
    json.dumps(data)


# ── the retrieval gate ────────────────────────────────────────────────────────
def test_is_citable_requires_a_source_and_a_hard_locator():
    assert is_citable(make_chunk())                                  # code + page
    assert is_citable(make_chunk(code="5-1", page_start=None))       # code alone
    assert is_citable(make_chunk(code=None, page_start=3))           # page alone


def test_is_citable_rejects_a_chunk_with_no_source_file():
    assert not is_citable(make_chunk(source_filename=""))


def test_is_citable_rejects_a_heading_only_chunk():
    """A heading is not a place an auditor can open — retrieval demands a code or a page."""
    assert not is_citable(make_chunk(code=None, page_start=None))


# ── the context gate ──────────────────────────────────────────────────────────
def test_citation_is_complete_accepts_any_single_locator():
    assert citation_is_complete(make_citation())
    assert citation_is_complete(make_citation(code=None, page_start=None))  # heading is enough here


def test_citation_is_complete_rejects_absent_and_unlocatable_citations():
    assert not citation_is_complete(None)
    assert not citation_is_complete(replace(make_citation(), source_filename=""))
    assert not citation_is_complete(make_citation(code=None, page_start=None, heading_path=()))


def test_the_context_gate_is_deliberately_looser_than_the_retrieval_gate():
    """Merge and parent-expansion build blocks from headings, so re-applying the retrieval
    gate downstream would drop citations retrieval had already validated."""
    heading_only = make_chunk(code=None, page_start=None)
    assert not is_citable(heading_only)
    assert citation_is_complete(build_citation(heading_only))


# ── diagnostics ───────────────────────────────────────────────────────────────
def test_missing_facets_reports_absent_fields_without_rejecting():
    assert missing_facets(make_citation(code=None, page_start=None)) == ["page", "code"]
    assert missing_facets(None) == ["citation"]


def test_missing_facets_is_empty_for_a_fully_faceted_citation():
    assert missing_facets(make_citation()) == []


# ── identity ──────────────────────────────────────────────────────────────────
def test_citation_key_distinguishes_places_clause_key_does_not():
    page_3 = make_citation(page_start=3, page_end=3)
    page_4 = make_citation(page_start=4, page_end=4)
    assert citation_key(page_3) != citation_key(page_4)  # different place
    assert clause_key(page_3) == clause_key(page_4)      # same clause


def test_citation_key_matches_for_two_chunks_of_the_same_place():
    assert citation_key(make_citation(chunk_id="c1")) == citation_key(make_citation(chunk_id="c2"))


def test_clause_key_separates_different_documents_and_codes():
    assert clause_key(make_citation()) != clause_key(make_citation(source_filename="ecc.pdf"))
    assert clause_key(make_citation()) != clause_key(make_citation(code="5-2"))


# ── derivation ────────────────────────────────────────────────────────────────
def test_respan_widens_the_span_refreshes_the_string_and_keeps_every_other_facet():
    original = make_citation()
    widened = respan(original, 3, 5)
    assert widened.page_start == 3 and widened.page_end == 5
    assert widened.formatted.endswith("pp. 3–5")
    assert widened.source_filename == original.source_filename
    assert widened.code == original.code
    assert widened.title == original.title
    assert widened.heading_path == original.heading_path
    assert widened.document_profile == original.document_profile


def test_respan_leaves_the_original_untouched():
    original = make_citation()
    respan(original, 3, 9)
    assert original.page_end == 3
    assert isinstance(original, Citation)
