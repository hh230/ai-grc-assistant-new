"""The Retrieval Engine — the orchestration that ties the stages together. It depends only
on the provider *ports* (`VectorSearchProvider`, `KeywordSearchProvider`); it has no idea
whether they're in-memory, pgvector, or anything else. The flow mirrors the approved
architecture: plan → (vector ∥ keyword, filtered) → RRF fusion → ranking → citation gate →
context assembly → RetrievedContext.

No generation, no LLM, no RAG — the output is a structured, cited context bundle and the
engine stops there.
"""

from __future__ import annotations

import time

from pipeline_contracts import TenancyError

from retrieval_engine import fusion, ranking
from retrieval_engine.citation import build_citation, is_citable
from retrieval_engine.planner import RetrievalPlan, RetrievalQuery, plan
from retrieval_engine.providers.corpus import in_scope
from retrieval_engine.providers.interfaces import (
    KeywordSearchProvider,
    RetrievedChunk,
    RetrievedContext,
    VectorSearchProvider,
)


class RetrievalEngine:
    def __init__(self, vector_provider: VectorSearchProvider, keyword_provider: KeywordSearchProvider) -> None:
        self._vector = vector_provider
        self._keyword = keyword_provider

    def retrieve(self, query: RetrievalQuery) -> RetrievedContext:
        started = time.perf_counter()
        p: RetrievalPlan = plan(query)
        timings: dict[str, float] = {}
        warnings: list[str] = []

        t = time.perf_counter()
        vector_hits = self._vector.search(p.normalized_query, p.filter, p.candidate_k)
        timings["vector_ms"] = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        keyword_hits = self._keyword.search(p.normalized_query, p.filter, p.candidate_k)
        timings["keyword_ms"] = (time.perf_counter() - t) * 1000

        # Defence in depth (ADR 0040 §4): the providers already scoped inside the store, but we
        # re-verify every candidate at the engine boundary. An out-of-scope chunk is a *failure*
        # — a scoping bug that would leak another tenant's data — never a silently dropped result.
        for hit in (*vector_hits, *keyword_hits):
            if not in_scope(hit.chunk, p.filter.scope):
                raise TenancyError(
                    f"retrieval admitted out-of-scope chunk {hit.chunk.chunk_id!r}; "
                    "refusing to proceed (ADR 0040 §4)"
                )

        fused = fusion.reciprocal_rank_fusion(
            {"vector": vector_hits, "keyword": keyword_hits}, weights=p.weights
        )
        total_candidates = len(fused)

        ranked = ranking.rank(fused, query_codes=p.codes, query_language=p.language)

        # ── citation gate ──
        citable = [r for r in ranked if is_citable(r.hit.chunk)]
        dropped = len(ranked) - len(citable)
        if dropped:
            warnings.append(f"{dropped} candidate(s) dropped for lacking a resolvable citation.")

        selected = citable[: p.final_k]
        top = selected[0].final_score if selected else 0.0

        results: list[RetrievedChunk] = []
        for r in selected:
            chunk = r.hit.chunk
            confidence = round(r.final_score / top, 4) if top > 0 else 0.0
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    citation=build_citation(chunk),
                    document_profile=chunk.document_profile,
                    structure_profile=chunk.structure_profile,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    scores={
                        "fused": round(r.hit.fused_score, 6),
                        "final": round(r.final_score, 6),
                        **{f"{k}_rank": v for k, v in r.hit.source_ranks.items()},
                        **r.boosts,
                    },
                    confidence=confidence,
                )
            )

        if not results:
            warnings.append("No citable results — insufficient evidence for this query and filter.")

        timings["total_ms"] = (time.perf_counter() - started) * 1000
        overall = round(min(1.0, top / (top + 1.0)), 4) if top > 0 else 0.0

        return RetrievedContext(
            query=query.text,
            results=results,
            total_candidates=total_candidates,
            applied_filter=p.filter,
            overall_confidence=overall,
            warnings=warnings,
            timings_ms={k: round(v, 2) for k, v in timings.items()},
        )
