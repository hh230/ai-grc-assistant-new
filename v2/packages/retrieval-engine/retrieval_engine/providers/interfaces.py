"""The ports and value objects the Retrieval Engine is built on. These are shared pipeline
contracts and live in the `pipeline-contracts` package; this module re-exports them so
every existing `retrieval_engine.providers.interfaces` import keeps working.

The engine depends only on these abstractions — it never imports a concrete provider, and
it has no idea whether vectors come from an in-memory array, pgvector, or anything else.
Swapping the in-memory providers for a `PgVectorProvider` is a wiring change; nothing in
the engine, planner, fusion, ranking, citation, or assembly changes.
"""

from __future__ import annotations

from pipeline_contracts.retrieval import (
    Citation,
    CorpusChunk,
    Filter,
    FusedHit,
    KeywordSearchProvider,
    RetrievedChunk,
    RetrievedContext,
    ScoredHit,
    VectorSearchProvider,
)

__all__ = [
    "Filter",
    "CorpusChunk",
    "ScoredHit",
    "FusedHit",
    "Citation",
    "RetrievedChunk",
    "RetrievedContext",
    "VectorSearchProvider",
    "KeywordSearchProvider",
]
