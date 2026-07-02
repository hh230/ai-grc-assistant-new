"""Unit tests for the knowledge retriever: grounded, bounded, cited context assembly."""
from __future__ import annotations

import pytest
from grc_domain.knowledge import (
    KnowledgeObject,
    KnowledgeObjectType,
    KnowledgeScope,
    ProvenanceRecord,
    SectionType,
    StructuralAnchor,
)
from grc_domain.shared.identifiers import (
    CanonicalKnowledgeObjectId,
    KnowledgeObjectId,
    KnowledgeSourceVersionId,
)
from grc_rag import KnowledgeRetriever

SCOPE = KnowledgeScope.global_()
VER = KnowledgeSourceVersionId("ver-1")


def obj(
    object_key: str,
    text: str,
    object_type: KnowledgeObjectType = KnowledgeObjectType.REQUIREMENT,
    *,
    anchor_code: str | None = None,
) -> KnowledgeObject:
    anchor = StructuralAnchor(SectionType.ARTICLE, anchor_code) if anchor_code else None
    provenance = ProvenanceRecord(source_version_id=VER, anchor=anchor)
    return KnowledgeObject.extract(
        id=KnowledgeObjectId(object_key),
        canonical_id=CanonicalKnowledgeObjectId(f"c-{object_key}"),
        scope=SCOPE,
        object_type=object_type,
        source_version_id=VER,
        verbatim_text=text,
        provenance=provenance,
    )


def retriever() -> KnowledgeRetriever:
    r = KnowledgeRetriever(SCOPE)
    r.add(obj("req-1", "The organization shall maintain an asset inventory.", anchor_code="5"))
    r.add(obj("req-2", "The organization shall encrypt data at rest.", anchor_code="6"))
    r.add(
        obj(
            "def-1",
            "Asset means anything of value to the organization.",
            KnowledgeObjectType.DEFINITION,
            anchor_code="2",
        )
    )
    return r


def test_retrieve_returns_grounded_chunks() -> None:
    context = retriever().retrieve("asset inventory")
    assert not context.is_empty
    top = context.chunks[0]
    assert top.object_id == KnowledgeObjectId("req-1")
    assert top.source_version_id == VER
    assert top.anchor == "5"


def test_retrieve_filters_by_type() -> None:
    context = retriever().retrieve("asset", object_type=KnowledgeObjectType.DEFINITION)
    assert {chunk.object_id for chunk in context.chunks} == {KnowledgeObjectId("def-1")}


def test_retrieve_respects_top_k() -> None:
    context = retriever().retrieve("organization shall asset data", top_k=1)
    assert len(context.chunks) == 1


def test_retrieve_respects_char_budget() -> None:
    # A tiny budget admits only the first chunk (the budget never drops the first hit).
    context = retriever().retrieve("organization shall asset data", max_total_chars=10)
    assert len(context.chunks) == 1


def test_grounded_text_includes_citation_keys() -> None:
    context = retriever().retrieve("asset inventory")
    assert "[req-1]" in context.grounded_text()


def test_empty_query_yields_empty_context() -> None:
    context = retriever().retrieve("")
    assert context.is_empty
    assert context.grounded_text() == ""


def test_retrieve_rejects_bad_arguments() -> None:
    with pytest.raises(ValueError, match="top_k"):
        retriever().retrieve("asset", top_k=0)
    with pytest.raises(ValueError, match="max_total_chars"):
        retriever().retrieve("asset", max_total_chars=0)
