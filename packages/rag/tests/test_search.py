"""Unit tests for the lexical knowledge search index."""
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
from grc_rag import CrossScopeError, LexicalSearchIndex

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


def populated_index() -> LexicalSearchIndex:
    index = LexicalSearchIndex(SCOPE)
    index.index(obj("req-1", "The organization shall maintain an asset inventory of all assets."))
    index.index(
        obj(
            "ctl-1",
            "Implement access control policies for all systems.",
            KnowledgeObjectType.CONTROL,
        )
    )
    index.index(
        obj(
            "def-1",
            "Personal data means information relating to an identified person.",
            KnowledgeObjectType.DEFINITION,
        )
    )
    index.index(obj("req-2", "The organization shall encrypt personal data at rest."))
    return index


def test_index_size() -> None:
    assert populated_index().size == 4


def test_search_ranks_relevant_object_first() -> None:
    results = populated_index().search("asset inventory")
    assert results
    assert results[0].object_id == KnowledgeObjectId("req-1")
    assert results[0].score > 0.0


def test_search_finds_all_matches() -> None:
    ids = {result.object_id for result in populated_index().search("personal data")}
    assert ids == {KnowledgeObjectId("def-1"), KnowledgeObjectId("req-2")}


def test_search_filters_by_object_type() -> None:
    results = populated_index().search("personal data", object_type=KnowledgeObjectType.DEFINITION)
    assert {r.object_id for r in results} == {KnowledgeObjectId("def-1")}


def test_search_empty_query_returns_nothing() -> None:
    assert populated_index().search("") == ()
    assert populated_index().search("the and of") == ()  # all stopwords


def test_search_no_match_returns_nothing() -> None:
    assert populated_index().search("quantum biology") == ()


def test_search_respects_limit() -> None:
    results = populated_index().search("organization shall personal data asset", limit=1)
    assert len(results) == 1


def test_search_rejects_nonpositive_limit() -> None:
    with pytest.raises(ValueError, match="limit"):
        populated_index().search("asset", limit=0)


def test_cross_scope_indexing_is_rejected() -> None:
    index = LexicalSearchIndex(SCOPE)
    with pytest.raises(CrossScopeError):
        index.index(obj("x", "some text", scope=ORG_SCOPE))
