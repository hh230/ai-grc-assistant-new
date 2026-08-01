from __future__ import annotations

from retrieval_engine.providers.corpus import passes_filter
from retrieval_engine.providers.interfaces import Filter


# ── metadata filtering ────────────────────────────────────────────────────────
def test_filter_by_profile(corpus):
    out = corpus.filter(Filter(document_profiles=("control_framework",)))
    assert {c.chunk_id for c in out} == {"c5"}


def test_filter_by_category_and_language(corpus):
    out = corpus.filter(Filter(categories=("Saudi Regulations",), languages=("ar",)))
    assert {c.chunk_id for c in out} == {"c5"}


def test_filter_by_code_prefix(corpus):
    out = corpus.filter(Filter(codes=("A.5",)))
    assert {c.chunk_id for c in out} == {"c1", "c3", "c4"}  # A.5.15, A.5.24, A.5.19


def test_empty_filter_matches_all(corpus, sample_chunks):
    assert len(corpus.filter(Filter())) == len(sample_chunks)


def test_passes_filter_direct(sample_chunks):
    c1 = sample_chunks[0]
    assert passes_filter(c1, Filter(document_profiles=("iso_standard",)))
    assert not passes_filter(c1, Filter(document_profiles=("law",)))


# ── keyword / BM25 ────────────────────────────────────────────────────────────
def test_keyword_ranks_relevant_chunk_first(keyword_provider):
    hits = keyword_provider.search("access control policy", Filter(), top_k=5)
    assert hits[0].chunk.chunk_id == "c1"
    assert all(h.source == "keyword" for h in hits)


def test_keyword_respects_filter(keyword_provider):
    # restrict to Arabic control_framework: only c5 is eligible
    hits = keyword_provider.search("الوصول", Filter(languages=("ar",)), top_k=5)
    assert [h.chunk.chunk_id for h in hits] == ["c5"]


def test_keyword_field_boost_prefers_title_code_match(keyword_provider):
    # "incident" appears in c3's text and title → should surface c3
    hits = keyword_provider.search("incident response", Filter(), top_k=3)
    assert hits[0].chunk.chunk_id == "c3"


def test_keyword_no_match_returns_empty(keyword_provider):
    assert keyword_provider.search("nonexistentterm zzz", Filter(), top_k=5) == []


# ── vector (with stubbed embedder for deterministic cosine) ───────────────────
def test_vector_returns_targeted_chunk_first(vector_provider):
    hits = vector_provider.search("query vector-target-c3", Filter(), top_k=6)
    assert hits[0].chunk.chunk_id == "c3"  # cosine=1.0 with its own vector
    assert all(h.source == "vector" for h in hits)


def test_vector_respects_filter(vector_provider):
    hits = vector_provider.search("query vector-target-c1", Filter(languages=("ar",)), top_k=6)
    assert {h.chunk.chunk_id for h in hits} == {"c5"}  # only Arabic chunk survives the filter
