"""Shared fixtures + builders.

Unit tests use synthetic `RetrievedChunk`s (no corpus, no I/O) so each stage is tested in
isolation and deterministically. Integration tests use the real knowledge corpus + Retrieval
Engine, and **skip cleanly** when the artifacts aren't present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from retrieval_engine import Citation, RetrievedChunk, RetrievedContext
from retrieval_engine.providers.interfaces import Filter

_V2 = Path(__file__).resolve().parents[3]  # tests → context-builder → packages → v2


def make_citation(
    *,
    source_filename: str = "iso27001.pdf",
    category: str = "ISO",
    document_profile: str | None = "iso_standard",
    structure_profile: str = "standard_clause",
    code: str | None = "A.5.15",
    title: str | None = "Access control",
    heading_path: tuple[str, ...] = ("5 Controls", "5.15 Access control"),
    page_start: int | None = 12,
    page_end: int | None = 12,
) -> Citation:
    formatted = f"{source_filename} — {code or title or ''} — p. {page_start}"
    return Citation(
        source_filename=source_filename,
        category=category,
        document_profile=document_profile,
        structure_profile=structure_profile,
        code=code,
        title=title,
        heading_path=heading_path,
        page_start=page_start,
        page_end=page_end,
        formatted=formatted,
    )


def make_chunk(
    chunk_id: str,
    text: str,
    *,
    document_id: str = "doc-iso",
    document_profile: str | None = "iso_standard",
    structure_profile: str = "standard_clause",
    code: str | None = "A.5.15",
    title: str | None = "Access control",
    heading_path: tuple[str, ...] = ("5 Controls", "5.15 Access control"),
    page_start: int | None = 12,
    page_end: int | None = 12,
    score: float = 1.0,
    confidence: float = 1.0,
    source_filename: str = "iso27001.pdf",
    category: str = "ISO",
) -> RetrievedChunk:
    citation = make_citation(
        source_filename=source_filename, category=category, document_profile=document_profile,
        structure_profile=structure_profile, code=code, title=title, heading_path=heading_path,
        page_start=page_start, page_end=page_end,
    )
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        citation=citation,
        document_profile=document_profile,
        structure_profile=structure_profile,
        page_start=page_start,
        page_end=page_end,
        scores={"final": score, "fused": score},
        confidence=confidence,
    )


def make_context(chunks: list[RetrievedChunk], *, query: str = "q", warnings: list[str] | None = None) -> RetrievedContext:
    return RetrievedContext(
        query=query,
        results=chunks,
        total_candidates=len(chunks),
        applied_filter=Filter(),
        overall_confidence=0.9,
        warnings=warnings or [],
        timings_ms={},
    )


# ── real-corpus fixtures (integration) ────────────────────────────────────────
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

    vector = InMemoryVectorProvider.load(corpus, embeddings_dir)
    keyword = InMemoryKeywordProvider(corpus)
    return RetrievalEngine(vector, keyword)
