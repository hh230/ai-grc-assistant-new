"""Unit tests for the agent roster (with deterministic fakes)."""
from __future__ import annotations

import pytest
from grc_agents import (
    AgentRole,
    AgentTask,
    ComplianceAgent,
    KnowledgeAgent,
    PolicyAgent,
)
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

SCOPE = KnowledgeScope.global_()
VER = KnowledgeSourceVersionId("ver-1")
PROV = ProvenanceRecord(source_version_id=VER)


def task(goal: str = "Summarize the control requirements.") -> AgentTask:
    return AgentTask(goal=goal)


# --- task validation -----------------------------------------------------------------------
def test_task_requires_goal() -> None:
    with pytest.raises(ValueError, match="goal"):
        AgentTask(goal="   ")


# --- reasoning agents ----------------------------------------------------------------------
async def test_compliance_agent_parses_structured_output() -> None:
    chat = FakeChatModel(responses=['{"output": "Two controls are unmet.", "confidence": 0.8}'])
    result = await ComplianceAgent(chat).run(task())
    assert result.role is AgentRole.COMPLIANCE
    assert result.output == "Two controls are unmet."
    assert result.confidence == 0.8
    assert result.requires_human_approval is False


async def test_invalid_json_yields_empty_low_confidence() -> None:
    result = await ComplianceAgent(FakeChatModel(responses=["not json"])).run(task())
    assert result.output == ""
    assert result.confidence == 0.0


async def test_policy_agent_output_requires_human_approval() -> None:
    chat = FakeChatModel(responses=['{"output": "Draft policy text.", "confidence": 0.7}'])
    result = await PolicyAgent(chat).run(task("Draft an access control policy."))
    assert result.requires_human_approval is True  # consequential


async def test_agent_sends_json_request() -> None:
    chat = FakeChatModel(responses=['{"output": "x", "confidence": 0.5}'])
    await ComplianceAgent(chat).run(task())
    assert chat.requests[0].json_object is True
    assert chat.requests[0].prompt_version is not None


# --- knowledge agent (grounded via RAG) ----------------------------------------------------
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


async def test_knowledge_agent_returns_grounded_cited_answer() -> None:
    retriever = KnowledgeRetriever(SCOPE)
    retriever.add(obj("req-2", "The organization shall encrypt data at rest."))
    rag_chat = FakeChatModel(
        responses=['{"answer": "Encrypt data at rest.", "citations": ["req-2"], "confidence": 0.9}']
    )
    agent = KnowledgeAgent(RagPipeline(retriever, rag_chat))

    result = await agent.run(task("data at rest"))
    assert result.role is AgentRole.KNOWLEDGE
    assert result.output == "Encrypt data at rest."
    assert result.citations == ("req-2",)
    assert result.requires_human_approval is False
