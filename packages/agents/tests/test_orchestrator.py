"""Unit tests for the AI Orchestrator: routing, decision trail, and human gates."""
from __future__ import annotations

import pytest
from grc_agents import (
    AgentRole,
    ComplianceAgent,
    NoAgentForRoleError,
    Orchestrator,
    PolicyAgent,
    ReportAgent,
    RiskAgent,
)
from grc_llm import FakeChatModel


def chat(output: str = "result", confidence: float = 0.7) -> FakeChatModel:
    return FakeChatModel(responses=[f'{{"output": "{output}", "confidence": {confidence}}}'])


def orchestrator() -> Orchestrator:
    shared = chat()
    return Orchestrator(
        [
            ComplianceAgent(shared),
            RiskAgent(shared),
            PolicyAgent(shared),
            ReportAgent(shared),
        ]
    )


# --- routing -------------------------------------------------------------------------------
def test_plan_routes_by_keyword() -> None:
    orch = orchestrator()
    assert orch.plan("Assess the risk of data loss") is AgentRole.RISK
    assert orch.plan("Draft a security policy") is AgentRole.POLICY
    assert orch.plan("Run a control gap analysis") is AgentRole.COMPLIANCE
    assert orch.plan("Produce an executive report") is AgentRole.REPORT


def test_plan_defaults_to_knowledge_when_available() -> None:
    orch = Orchestrator([ComplianceAgent(chat()), KnowledgeFallback()])
    assert orch.plan("what does the evidence say about backups") is AgentRole.KNOWLEDGE


def test_plan_raises_when_no_agent() -> None:
    orch = Orchestrator([ComplianceAgent(chat())])
    with pytest.raises(NoAgentForRoleError):
        orch.plan("tell me a story")  # no keyword match, no knowledge agent


# --- run / decision trail / human gate -----------------------------------------------------
async def test_run_records_decision_trail() -> None:
    outcome = await orchestrator().run("Run a control gap analysis")
    assert outcome.route is AgentRole.COMPLIANCE
    steps = [decision.step for decision in outcome.decisions]
    assert steps[:2] == ["plan", "execute"]
    assert outcome.awaiting_approval is False


async def test_consequential_route_is_gated_for_approval() -> None:
    outcome = await orchestrator().run("Draft an access control policy")
    assert outcome.route is AgentRole.POLICY
    assert outcome.awaiting_approval is True
    assert any(decision.step == "human_gate" for decision in outcome.decisions)


async def test_explicit_role_overrides_planning() -> None:
    outcome = await orchestrator().run("anything", role=AgentRole.RISK)
    assert outcome.route is AgentRole.RISK


async def test_run_rejects_empty_goal() -> None:
    with pytest.raises(ValueError, match="goal"):
        await orchestrator().run("   ")


# --- a tiny knowledge-role stand-in (avoids building a full RAG pipeline here) --------------
class KnowledgeFallback(ComplianceAgent):
    """A stand-in agent registered under the KNOWLEDGE role for routing-default tests."""

    def __init__(self) -> None:
        super().__init__(chat())

    @property
    def role(self) -> AgentRole:
        return AgentRole.KNOWLEDGE
