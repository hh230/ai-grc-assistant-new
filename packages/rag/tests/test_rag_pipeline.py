"""Unit tests for the RAG pipeline: grounded generation with citation validation (fake LLM)."""
from __future__ import annotations

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
)
from grc_llm import FakeChatModel
from grc_rag import KnowledgeRetriever, RagPipeline
from grc_rag.prompts import ANSWER_QUESTION_VERSION

SCOPE = KnowledgeScope.global_()
VER = KnowledgeSourceVersionId("ver-1")
PROV = ProvenanceRecord(source_version_id=VER)


def obj(object_key: str, text: str) -> KnowledgeObject:
    return KnowledgeObject.extract(
        id=KnowledgeObjectId(object_key),
        canonical_id=CanonicalKnowledgeObjectId(f"c-{object_key}"),
        scope=SCOPE,
        object_type=KnowledgeObjectType.REQUIREMENT,
        source_version_id=VER,
        verbatim_text=text,
        provenance=PROV,
    )


def retriever() -> KnowledgeRetriever:
    r = KnowledgeRetriever(SCOPE)
    r.add(obj("req-1", "The organization shall maintain an asset inventory."))
    r.add(obj("req-2", "The organization shall encrypt data at rest."))
    return r


def pipeline(*responses: str) -> tuple[RagPipeline, FakeChatModel]:
    chat = FakeChatModel(responses=list(responses))
    return RagPipeline(retriever(), chat), chat


async def test_returns_grounded_cited_answer() -> None:
    pipe, chat = pipeline(
        '{"answer": "Encrypt data at rest.", "citations": ["req-2"], "confidence": 0.9}'
    )
    answer = await pipe.answer("data at rest")

    assert answer.insufficient_evidence is False
    assert answer.answer == "Encrypt data at rest."
    assert [c.object_id for c in answer.citations] == [KnowledgeObjectId("req-2")]
    assert answer.citations[0].source_version_id == VER
    assert answer.confidence == 0.9
    assert len(chat.requests) == 1


async def test_request_is_json_mode_with_prompt_version() -> None:
    pipe, chat = pipeline('{"answer": "x", "citations": ["req-2"], "confidence": 0.5}')
    await pipe.answer("data at rest")
    assert chat.requests[0].json_object is True
    assert chat.requests[0].prompt_version == ANSWER_QUESTION_VERSION
    assert chat.requests[0].temperature == 0.0


async def test_no_retrieval_yields_insufficient_without_calling_model() -> None:
    pipe, chat = pipeline()  # default response would be valid-but-empty, but retrieval is empty
    answer = await pipe.answer("nonexistent topic about marine biology")
    assert answer.insufficient_evidence is True
    assert len(chat.requests) == 0  # the model is never called when nothing is retrieved


async def test_uncited_answer_is_rejected_as_insufficient() -> None:
    # The model cites a key that was not in the retrieved context — it must be dropped.
    pipe, _ = pipeline('{"answer": "Trust me.", "citations": ["ghost-99"], "confidence": 0.95}')
    answer = await pipe.answer("data at rest")
    assert answer.insufficient_evidence is True
    assert answer.citations == ()


async def test_invalid_json_fails_safe_to_insufficient() -> None:
    pipe, _ = pipeline("this is not json")
    answer = await pipe.answer("data at rest")
    assert answer.insufficient_evidence is True


async def test_hallucinated_citation_is_filtered_but_valid_one_kept() -> None:
    pipe, _ = pipeline(
        '{"answer": "Encrypt at rest.", "citations": ["req-2", "ghost-1"], "confidence": 0.8}'
    )
    answer = await pipe.answer("data at rest")
    assert answer.insufficient_evidence is False
    assert [c.object_id for c in answer.citations] == [KnowledgeObjectId("req-2")]
