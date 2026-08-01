"""Turns a `RetrievalQuery` into a `RetrievalPlan`: normalize the query, decide the
metadata filter, over-fetch depth for the candidate stage, final result count, and the
fusion weights. Pure and deterministic. A Decision Engine `DecisionPlan` can populate the
filter (profiles), `top_k`, and language — but this planner stays self-contained so
retrieval is usable on its own.

Default weights deliberately favour keyword over vector, because the current corpus vectors
are the non-semantic Phase-4 hash embeddings (see providers/vector.py). When real
embeddings land, the default rebalances — nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass

# RetrievalQuery is a shared pipeline contract (the Decision → Retrieval hand-off shape);
# it lives in pipeline-contracts and is re-exported here for backward compatibility.
from pipeline_contracts.retrieval import DEFAULT_TOP_K, RetrievalQuery

from retrieval_engine.providers.interfaces import Filter
from retrieval_engine.text import normalize

CANDIDATE_MULTIPLIER = 5
DEFAULT_WEIGHTS = {"vector": 0.4, "keyword": 1.0}

__all__ = ["RetrievalQuery", "RetrievalPlan", "plan", "DEFAULT_TOP_K", "CANDIDATE_MULTIPLIER", "DEFAULT_WEIGHTS"]


@dataclass(frozen=True)
class RetrievalPlan:
    query_text: str
    normalized_query: str
    filter: Filter
    candidate_k: int
    final_k: int
    weights: dict[str, float]
    language: str | None
    codes: tuple[str, ...]


def plan(query: RetrievalQuery) -> RetrievalPlan:
    final_k = max(1, query.top_k)
    return RetrievalPlan(
        query_text=query.text,
        normalized_query=normalize(query.text),
        filter=query.filter,
        candidate_k=final_k * CANDIDATE_MULTIPLIER,
        final_k=final_k,
        weights=query.weights or dict(DEFAULT_WEIGHTS),
        language=query.language,
        codes=query.codes,
    )
