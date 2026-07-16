"""Reciprocal Rank Fusion. The vector and keyword providers produce scores on
non-comparable scales (cosine vs. BM25), so we fuse on *rank*, not raw score — scale-free
and robust. `score(d) = Σ_r w_r / (k + rank_r(d))`. Fully explainable: every fused hit
keeps its per-source rank and score."""

from __future__ import annotations

from retrieval_engine.providers.interfaces import FusedHit, ScoredHit

RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[ScoredHit]],
    weights: dict[str, float] | None = None,
    k: int = RRF_K,
) -> list[FusedHit]:
    weights = weights or {}
    fused_score: dict[str, float] = {}
    source_scores: dict[str, dict[str, float]] = {}
    source_ranks: dict[str, dict[str, int]] = {}
    chunk_by_id: dict[str, ScoredHit] = {}

    for source, hits in ranked_lists.items():
        w = weights.get(source, 1.0)
        for rank, hit in enumerate(hits, start=1):
            cid = hit.chunk.chunk_id
            fused_score[cid] = fused_score.get(cid, 0.0) + w / (k + rank)
            source_scores.setdefault(cid, {})[source] = hit.score
            source_ranks.setdefault(cid, {})[source] = rank
            chunk_by_id[cid] = hit  # any hit carries the same chunk payload

    fused = [
        FusedHit(
            chunk=chunk_by_id[cid].chunk,
            fused_score=score,
            source_scores=source_scores[cid],
            source_ranks=source_ranks[cid],
        )
        for cid, score in fused_score.items()
    ]
    fused.sort(key=lambda f: f.fused_score, reverse=True)
    return fused
