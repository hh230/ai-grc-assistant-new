from __future__ import annotations

from retrieval_engine import Filter, RetrievalEngine, RetrievalQuery
from retrieval_engine.citation import build_citation, is_citable
from retrieval_engine.fusion import reciprocal_rank_fusion
from retrieval_engine.providers.interfaces import CorpusChunk, ScoredHit
from retrieval_engine.ranking import rank

from tests.conftest import make_chunk


# ── fusion ────────────────────────────────────────────────────────────────────
def test_rrf_rewards_agreement_across_sources(sample_chunks):
    c1, c2, c3 = sample_chunks[0], sample_chunks[1], sample_chunks[2]
    vector = [ScoredHit(c2, 0.9, "vector"), ScoredHit(c1, 0.8, "vector")]
    keyword = [ScoredHit(c1, 5.0, "keyword"), ScoredHit(c3, 3.0, "keyword")]
    fused = reciprocal_rank_fusion({"vector": vector, "keyword": keyword})
    # c1 appears in both lists → should fuse to the top
    assert fused[0].chunk.chunk_id == "c1"
    assert "vector" in fused[0].source_ranks and "keyword" in fused[0].source_ranks


def test_rrf_weights_shift_ranking(sample_chunks):
    c1, c2 = sample_chunks[0], sample_chunks[1]
    lists = {"vector": [ScoredHit(c2, 1.0, "vector")], "keyword": [ScoredHit(c1, 1.0, "keyword")]}
    keyword_heavy = reciprocal_rank_fusion(lists, weights={"vector": 0.1, "keyword": 1.0})
    assert keyword_heavy[0].chunk.chunk_id == "c1"
    vector_heavy = reciprocal_rank_fusion(lists, weights={"vector": 1.0, "keyword": 0.1})
    assert vector_heavy[0].chunk.chunk_id == "c2"


# ── ranking boosts ────────────────────────────────────────────────────────────
def test_exact_code_boost_pins_matching_clause():
    a = make_chunk("a", "some access text", code="A.5.15")
    b = make_chunk("b", "other access text", code="A.5.19")
    fused = reciprocal_rank_fusion({"keyword": [ScoredHit(b, 5.0, "keyword"), ScoredHit(a, 4.0, "keyword")]})
    ranked = rank(fused, query_codes=("A.5.15",))
    assert ranked[0].hit.chunk.chunk_id == "a"  # exact-code boost overtakes b
    assert "exact_code" in ranked[0].boosts


def test_heading_only_penalized():
    heading = make_chunk("h", "bare heading", content_type="heading_only")
    fused = reciprocal_rank_fusion({"keyword": [ScoredHit(heading, 5.0, "keyword")]})
    ranked = rank(fused)
    assert ranked[0].boosts.get("heading_only") is not None


# ── citation validation ───────────────────────────────────────────────────────
def test_citation_requires_source_and_locator():
    ok = make_chunk("ok", "text", code="A.5.15", page=12)
    no_source = make_chunk("ns", "text", code="A.5.15")
    no_source = CorpusChunk(**{**no_source.__dict__, "source_filename": ""})
    no_locator = make_chunk("nl", "text", code=None, page=None)
    assert is_citable(ok)
    assert not is_citable(no_source)
    assert not is_citable(no_locator)


def test_citation_formatting():
    chunk = make_chunk("c", "Access control", code="A.5.15", page=12)
    citation = build_citation(chunk)
    assert citation.formatted.startswith("ISO 27001.pdf — A.5.15")
    assert "p. 12" in citation.formatted


# ── full engine ───────────────────────────────────────────────────────────────
def test_engine_end_to_end_returns_cited_context(vector_provider, keyword_provider):
    engine = RetrievalEngine(vector_provider, keyword_provider)
    ctx = engine.retrieve(RetrievalQuery(text="access control policy", top_k=3))
    assert ctx.query == "access control policy"
    assert len(ctx.results) >= 1
    assert ctx.results[0].chunk_id == "c1"
    assert ctx.results[0].citation.formatted  # every surfaced result is cited
    assert "total_ms" in ctx.timings_ms


def test_engine_drops_non_citable_chunks(vector_provider, keyword_provider):
    engine = RetrievalEngine(vector_provider, keyword_provider)
    # c6 is a heading-only chunk with no code and no page → not citable → never surfaced
    ctx = engine.retrieve(RetrievalQuery(text="bare heading", top_k=6))
    assert all(r.chunk_id != "c6" for r in ctx.results)


def test_engine_filter_scopes_results(vector_provider, keyword_provider):
    engine = RetrievalEngine(vector_provider, keyword_provider)
    ctx = engine.retrieve(RetrievalQuery(text="الوصول", filter=Filter(languages=("ar",)), top_k=5))
    assert [r.chunk_id for r in ctx.results] == ["c5"]


def test_engine_insufficient_evidence_warns(vector_provider, keyword_provider):
    engine = RetrievalEngine(vector_provider, keyword_provider)
    ctx = engine.retrieve(RetrievalQuery(text="zzzznomatch", filter=Filter(categories=("Nonexistent",)), top_k=5))
    assert ctx.results == []
    assert any("insufficient evidence" in w.lower() for w in ctx.warnings)


def test_engine_works_with_any_port_implementation(keyword_provider):
    # a fake vector provider proves the engine depends only on the port, not the adapter
    class FakeVector:
        def search(self, query, filter, top_k):
            return []

    engine = RetrievalEngine(FakeVector(), keyword_provider)
    ctx = engine.retrieve(RetrievalQuery(text="access control", top_k=3))
    assert len(ctx.results) >= 1  # keyword alone still produces cited results


def test_engine_is_deterministic(vector_provider, keyword_provider):
    engine = RetrievalEngine(vector_provider, keyword_provider)
    a = engine.retrieve(RetrievalQuery(text="risk assessment", top_k=3)).to_dict()
    b = engine.retrieve(RetrievalQuery(text="risk assessment", top_k=3)).to_dict()
    # results are deterministic; wall-clock timings are not, so compare everything else
    a.pop("timings_ms"), b.pop("timings_ms")
    assert a == b
