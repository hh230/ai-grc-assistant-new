"""Shared builders. Unit tests construct synthetic `DecisionPlan`s and `ContextPackage`s
directly (fast, deterministic, no engines). An optional real-corpus fixture backs the
integration/benchmark tests and skips cleanly when artifacts are absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from context_builder import ContextBuilder, WorkflowPolicy
from decision_engine import DecisionPlan
from retrieval_engine import Citation, RetrievedChunk, RetrievedContext
from retrieval_engine.providers.interfaces import Filter

_V2 = Path(__file__).resolve().parents[3]


def make_plan(
    intent: str = "gap_assessment",
    *,
    requires_retrieval: bool = True,
    requires_document: bool = False,
    language: str = "en",
    reason: str = "matched cues",
) -> DecisionPlan:
    return DecisionPlan(
        intent=intent,
        workflow=f"{intent}_workflow",
        requires_retrieval=requires_retrieval,
        requires_document=requires_document,
        requires_reranker=False,
        requires_human_gate=False,
        multi_step=False,
        retrieval_passes=1 if requires_retrieval else 0,
        context_budget=8000,
        target_profiles=[],
        confidence=0.8,
        reason=reason,
        language=language,
    )


def _citation(source="iso27001.pdf", code="A.5.15", page=12, heading=("5 Controls", "5.15 Access control")):
    return Citation(
        source_filename=source, category="ISO", document_profile="iso_standard",
        structure_profile="standard_clause", code=code, title="Access control",
        heading_path=heading, page_start=page, page_end=page,
        formatted=f"{source} — {code} — p. {page}",
    )


def make_chunk(chunk_id, text, *, document_id="doc-iso", profile="iso_standard", code="A.5.15",
               source="iso27001.pdf", score=1.0) -> RetrievedChunk:
    cit = _citation(source=source, code=code)
    return RetrievedChunk(
        chunk_id=chunk_id, document_id=document_id, text=text, citation=cit,
        document_profile=profile, structure_profile="standard_clause",
        page_start=cit.page_start, page_end=cit.page_end,
        scores={"final": score}, confidence=score,
    )


def make_retrieved(chunks, *, query="q", warnings=None) -> RetrievedContext:
    return RetrievedContext(
        query=query, results=chunks, total_candidates=len(chunks), applied_filter=Filter(),
        overall_confidence=0.9, warnings=warnings or [], timings_ms={},
    )


def make_context_package(*, query="access control policy", n=3, workflow=WorkflowPolicy.GAP_ASSESSMENT):
    chunks = [
        make_chunk(f"c{i}", f"Clause {i}: access control requirement number {i}.",
                   document_id=f"doc{i}", code=f"A.5.{15 + i}", source=f"src{i}.pdf", score=1.0 - i * 0.05)
        for i in range(n)
    ]
    return ContextBuilder().build(make_retrieved(chunks, query=query), workflow=workflow, budget=8000)


# ── real corpus (integration/benchmark) ──────────────────────────────────────
@pytest.fixture(scope="session")
def corpus():
    chunks_dir = _V2 / "knowledge" / "chunks"
    if not chunks_dir.exists():
        pytest.skip("knowledge chunk artifacts not present")
    from retrieval_engine.providers.corpus import InMemoryCorpus

    return InMemoryCorpus.load(chunks_dir)


@pytest.fixture(scope="session")
def retrieval_engine(corpus):
    embeddings_dir = _V2 / "knowledge" / "embeddings"
    if not embeddings_dir.exists():
        pytest.skip("embedding artifacts not present")
    from retrieval_engine import RetrievalEngine
    from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
    from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider

    return RetrievalEngine(InMemoryVectorProvider.load(corpus, embeddings_dir), InMemoryKeywordProvider(corpus))
