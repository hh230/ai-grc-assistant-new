"""Fixtures that build the **real** in-memory retrieval providers from `retrieval-engine` over a
small GRC corpus — so the search tools run against the genuine engine, not mocks. The base corpus is
all GLOBAL (shared) knowledge; the tenant-isolation test adds a foreign-tenant chunk of its own."""

from __future__ import annotations

import numpy as np
import pytest
from pipeline_contracts import KnowledgeScope, TenantContext
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider
from retrieval_engine.providers.interfaces import CorpusChunk


def make_chunk(
    chunk_id: str, text: str, *, code: str | None = None, org: str | None = None
) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        text=text,
        document_profile="iso_standard",
        structure_profile="standard_clause",
        category="ISO",
        language="en",
        code=code,
        title=text[:24],
        heading_path=("Clause 5", "5.1"),
        page_start=1,
        page_end=1,
        source_filename="ISO 27001.pdf",
        checksum="sum-" + chunk_id,
        content_type="section",
        scope_kind=KnowledgeScope.ORGANIZATION if org else KnowledgeScope.GLOBAL,
        organization_id=org,
    )


@pytest.fixture
def chunks() -> list[CorpusChunk]:
    return [
        make_chunk("c1", "access control policy for information security", code="A.5.15"),
        make_chunk("c2", "information security risk assessment and treatment", code="6.1"),
        make_chunk("c3", "incident management and response procedures", code="A.5.24"),
    ]


@pytest.fixture
def corpus(chunks: list[CorpusChunk]) -> InMemoryCorpus:
    return InMemoryCorpus.from_chunks(chunks)


@pytest.fixture
def keyword_provider(corpus: InMemoryCorpus) -> InMemoryKeywordProvider:
    return InMemoryKeywordProvider(corpus)


@pytest.fixture
def keyword_provider_with_foreign() -> InMemoryKeywordProvider:
    """A keyword provider whose corpus holds a shared chunk AND a *foreign tenant's* chunk that also
    matches — the fixture for proving tenant isolation."""
    corpus = InMemoryCorpus.from_chunks([
        make_chunk("shared", "access control policy", code="A.5.15"),
        make_chunk("foreign", "access control runbook", code="X.1", org="org_globex"),
    ])
    return InMemoryKeywordProvider(corpus)


@pytest.fixture
def vector_provider(corpus: InMemoryCorpus, chunks: list[CorpusChunk]) -> InMemoryVectorProvider:
    rng = np.random.RandomState(1)
    matrix = rng.rand(len(chunks), 8).astype("float32")
    ids = [c.chunk_id for c in chunks]

    def stub_embed(text: str, dim: int) -> list[float]:
        for i, cid in enumerate(ids):
            if f"target-{cid}" in text:
                return list(matrix[i].tolist())
        return list(matrix[0].tolist())

    return InMemoryVectorProvider(corpus, matrix, ids, embed_query=stub_embed)


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))
