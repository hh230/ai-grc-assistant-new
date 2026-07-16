"""Deduplication: chunk_id, checksum (identical normalized text), similarity, containment."""

from __future__ import annotations

from context_builder.builder import blocks_from_context
from context_builder.deduplicate import deduplicate, jaccard, normalize_text, token_set
from tests.conftest import make_chunk, make_context


def _blocks(*chunks):
    return blocks_from_context(make_context(list(chunks)))


def test_identical_text_is_deduplicated_by_checksum():
    blocks = _blocks(
        make_chunk("a", "Access control shall be enforced.", score=0.9),
        make_chunk("b", "Access  control   shall be enforced.", score=0.5, document_id="doc-2", source_filename="other.pdf"),
    )
    kept, removed = deduplicate(blocks)
    assert removed == 1
    assert len(kept) == 1
    assert kept[0].block_id == "a"  # higher score wins


def test_higher_score_representative_absorbs_provenance():
    kept, _ = deduplicate(_blocks(
        make_chunk("low", "same text here", score=0.2),
        make_chunk("high", "same text here", score=0.99, document_id="doc-2", source_filename="x.pdf"),
    ))
    assert kept[0].block_id == "high"
    assert set(kept[0].source_chunk_ids) == {"high", "low"}


def test_near_duplicate_by_similarity_is_removed():
    a = "The organization shall implement access control policies and procedures for all systems."
    b = "The organization shall implement access control policies and procedures for all systems today."
    kept, removed = deduplicate(_blocks(
        make_chunk("a", a, score=0.9),
        make_chunk("b", b, score=0.4, document_id="d2", source_filename="y.pdf"),
    ))
    assert removed == 1 and len(kept) == 1


def test_distinct_chunks_are_all_kept():
    kept, removed = deduplicate(_blocks(
        make_chunk("a", "Access control requirements for privileged accounts.", score=0.9),
        make_chunk("b", "Incident response and breach notification timelines.", score=0.8, document_id="d2"),
        make_chunk("c", "Cryptographic key management lifecycle.", score=0.7, document_id="d3"),
    ))
    assert removed == 0 and len(kept) == 3


def test_containment_only_collapses_within_same_document():
    short = "access control policy"
    long = "access control policy must be reviewed annually by the security committee and approved"
    # same doc → contained child removed
    kept, removed = deduplicate(_blocks(
        make_chunk("long", long, score=0.9, document_id="same"),
        make_chunk("short", short, score=0.3, document_id="same", code="A.5.16"),
    ))
    assert removed == 1
    # different docs → both kept (legitimately two citations)
    kept2, removed2 = deduplicate(_blocks(
        make_chunk("long", long, score=0.9, document_id="d1"),
        make_chunk("short", short, score=0.3, document_id="d2", source_filename="z.pdf"),
    ))
    assert removed2 == 0 and len(kept2) == 2


def test_normalize_and_jaccard_helpers():
    assert normalize_text("  Aç-cess,  Control! ") == "aç cess control"
    assert jaccard(token_set("a b c"), token_set("a b c")) == 1.0
    assert jaccard(token_set("a b"), token_set("c d")) == 0.0
