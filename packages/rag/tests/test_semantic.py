"""Unit tests for embedding-backed semantic search (with the deterministic fake embedder)."""
from __future__ import annotations

import pytest
from grc_domain.knowledge import (
    KnowledgeObject,
    KnowledgeObjectType,
    KnowledgeScope,
    ProvenanceRecord,
)
from grc_domain.shared.identifiers import (
    CanonicalKnowledgeObjectId,
    KnowledgeObjectId,
    KnowledgeSourceVersionId,
    OrganizationId,
)
from grc_llm import FakeEmbeddingModel
from grc_rag import CrossScopeError, SemanticSearchIndex

SCOPE = KnowledgeScope.global_()
ORG_SCOPE = KnowledgeScope.for_organization(OrganizationId("org-1"))
VER = KnowledgeSourceVersionId("ver-1")
PROV = ProvenanceRecord(source_version_id=VER)


def obj(
    object_key: str,
    text: str,
    object_type: KnowledgeObjectType = KnowledgeObjectType.REQUIREMENT,
    *,
    scope: KnowledgeScope = SCOPE,
) -> KnowledgeObject:
    return KnowledgeObject.extract(
        id=KnowledgeObjectId(object_key),
        canonical_id=CanonicalKnowledgeObjectId(f"c-{object_key}"),
        scope=scope,
        object_type=object_type,
        source_version_id=VER,
        verbatim_text=text,
        provenance=PROV,
    )


def index() -> SemanticSearchIndex:
    return SemanticSearchIndex(SCOPE, FakeEmbeddingModel(dimension=128))


async def test_ranks_semantically_similar_object_first() -> None:
    semantic = index()
    await semantic.index(obj("req-1", "the organization shall maintain an asset inventory"))
    await semantic.index(obj("req-2", "encryption keys must be rotated every ninety days"))

    hits = await semantic.search("an asset inventory maintained by the organization")
    assert hits[0].object_id == KnowledgeObjectId("req-1")
    assert hits[0].similarity >= hits[-1].similarity


async def test_empty_index_returns_nothing() -> None:
    assert await index().search("anything") == ()


async def test_filters_by_object_type() -> None:
    semantic = index()
    await semantic.index(obj("req-1", "maintain an asset inventory"))
    await semantic.index(
        obj("def-1", "asset means anything of value", KnowledgeObjectType.DEFINITION)
    )
    hits = await semantic.search("asset", object_type=KnowledgeObjectType.DEFINITION)
    assert {hit.object_id for hit in hits} == {KnowledgeObjectId("def-1")}


async def test_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="limit"):
        await index().search("asset", limit=0)


async def test_cross_scope_indexing_rejected() -> None:
    semantic = index()
    with pytest.raises(CrossScopeError):
        await semantic.index(obj("x", "text", scope=ORG_SCOPE))
