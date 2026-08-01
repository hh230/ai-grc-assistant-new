from __future__ import annotations

import numpy as np
import pytest
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider
from retrieval_engine.providers.interfaces import CorpusChunk


def make_chunk(
    chunk_id: str,
    text: str,
    *,
    code: str | None = None,
    profile: str = "iso_standard",
    structure: str = "standard_clause",
    category: str = "ISO",
    language: str = "en",
    page: int | None = 1,
    source: str = "ISO 27001.pdf",
    content_type: str = "section",
    title: str | None = None,
) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{source}",
        text=text,
        document_profile=profile,
        structure_profile=structure,
        category=category,
        language=language,
        code=code,
        title=title or text[:24],
        heading_path=("Clause 5", "5.1"),
        page_start=page,
        page_end=page,
        source_filename=source,
        checksum="sum-" + chunk_id,
        content_type=content_type,
    )


@pytest.fixture
def sample_chunks() -> list[CorpusChunk]:
    return [
        make_chunk("c1", "access control policy for information security", code="A.5.15"),
        make_chunk("c2", "information security risk assessment and treatment", code="6.1"),
        make_chunk("c3", "incident management and response procedures", code="A.5.24"),
        make_chunk("c4", "supplier and third party relationships security", code="A.5.19"),
        make_chunk("c5", "سياسة التحكم في الوصول وأمن المعلومات", code="1-1-1", language="ar",
                   profile="control_framework", category="Saudi Regulations", source="ECC.pdf"),
        make_chunk("c6", "a bare heading with no locator", code=None, page=None, content_type="heading_only", source="Guide.pdf"),
    ]


@pytest.fixture
def corpus(sample_chunks) -> InMemoryCorpus:
    return InMemoryCorpus.from_chunks(sample_chunks)


@pytest.fixture
def keyword_provider(corpus) -> InMemoryKeywordProvider:
    return InMemoryKeywordProvider(corpus)


@pytest.fixture
def vector_provider(corpus, sample_chunks) -> InMemoryVectorProvider:
    # deterministic pseudo-vectors; a stub embedder maps a query to a chosen row so cosine
    # ordering is controllable in tests.
    rng = np.random.RandomState(1)
    matrix = rng.rand(len(sample_chunks), 8).astype("float32")
    ids = [c.chunk_id for c in sample_chunks]

    def stub_embed(text: str, dim: int):
        # a query containing "vector-target-cN" returns exactly chunk cN's vector
        for i, cid in enumerate(ids):
            if f"target-{cid}" in text:
                return matrix[i].tolist()
        return matrix[0].tolist()

    return InMemoryVectorProvider(corpus, matrix, ids, embed_query=stub_embed)
