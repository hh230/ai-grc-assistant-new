"""Adjacent merge: same doc + heading + clause + consecutive pages; never across documents."""

from __future__ import annotations

from context_builder.builder import blocks_from_context
from context_builder.merge import merge_adjacent
from tests.conftest import make_chunk, make_context


def _blocks(*chunks):
    return blocks_from_context(make_context(list(chunks)))


def test_consecutive_same_clause_pages_merge():
    blocks = _blocks(
        make_chunk("p12", "First half of the clause.", page_start=12, page_end=12, score=0.9),
        make_chunk("p13", "Second half of the clause.", page_start=13, page_end=13, score=0.8),
    )
    merged, count = merge_adjacent(blocks)
    assert count == 1
    assert len(merged) == 1
    b = merged[0]
    assert "First half" in b.text and "Second half" in b.text
    assert b.page_start == 12 and b.page_end == 13
    assert b.citation.page_start == 12 and b.citation.page_end == 13  # citation respanned
    assert "pp. 12–13" in b.citation.formatted
    assert set(b.source_chunk_ids) == {"p12", "p13"}


def test_non_consecutive_pages_do_not_merge():
    blocks = _blocks(
        make_chunk("p12", "Clause text A.", page_start=12, page_end=12),
        make_chunk("p40", "Clause text B.", page_start=40, page_end=40),
    )
    merged, count = merge_adjacent(blocks)
    assert count == 0 and len(merged) == 2


def test_never_merge_across_documents():
    blocks = _blocks(
        make_chunk("a", "Shared clause text.", document_id="doc-1", page_start=1, page_end=1),
        make_chunk("b", "Shared clause text continued.", document_id="doc-2", page_start=2, page_end=2,
                   source_filename="other.pdf"),
    )
    merged, count = merge_adjacent(blocks)
    assert count == 0 and len(merged) == 2


def test_different_heading_same_page_does_not_merge():
    blocks = _blocks(
        make_chunk("a", "Under heading one.", code="A.5.15", heading_path=("5", "5.15"), page_start=3, page_end=3),
        make_chunk("b", "Under heading two.", code="A.5.16", heading_path=("5", "5.16"), page_start=3, page_end=3),
    )
    merged, count = merge_adjacent(blocks)
    assert count == 0 and len(merged) == 2


def test_unpaged_clause_fragments_merge():
    # laws/regulations: a code, no page image
    blocks = _blocks(
        make_chunk("a1", "Article 5 paragraph 1.", page_start=None, page_end=None, code="Art.5",
                   heading_path=("Chapter 2", "Article 5")),
        make_chunk("a2", "Article 5 paragraph 2.", page_start=None, page_end=None, code="Art.5",
                   heading_path=("Chapter 2", "Article 5")),
    )
    merged, count = merge_adjacent(blocks)
    assert count == 1 and len(merged) == 1
