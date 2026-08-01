from __future__ import annotations

from devteam_protocol import (
    Agent,
    AgentArtifact,
    AgentDecision,
    AgentFinding,
    AgentHandoff,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
    FindingSeverity,
    agent_request_from_step,
    agent_result_to_step,
)
from mission_engine.ports import StepRequest, StepResult
from pipeline_contracts import TenantContext


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="platform", principal_id="foreman")


def test_agent_request_is_built_from_a_step_reusing_the_core() -> None:
    step = StepRequest(
        mission_id="m1",
        step_id="s1",
        tenant=_tenant(),
        instruction="run the quality gate",
        consequential=False,
        tool="qa",
    )
    req = agent_request_from_step(step, role=AgentRole.QA)
    assert req.role is AgentRole.QA
    assert req.intent == "run the quality gate"
    assert req.tenant is step.tenant  # reused, not re-derived
    assert req.mission_id == "m1"
    assert req.step_id == "s1"
    assert req.consequential is False


def test_agent_result_folds_down_to_a_core_step_result() -> None:
    result = AgentResult(
        ok=True,
        output="3 passed",
        artifacts=(AgentArtifact(kind="test_log", title="pytest", content="..."),),
        findings=(AgentFinding(kind="flaky", severity=FindingSeverity.LOW, summary="x"),),
        source_ids=("run/1",),
        confidence=0.9,
    )
    step_result = agent_result_to_step(result, step_id="s1")
    assert isinstance(step_result, StepResult)
    assert step_result.step_id == "s1"
    assert step_result.ok is True
    assert step_result.output == "3 passed"
    assert step_result.source_ids == ("run/1",)
    # the richer collaboration layer is intentionally NOT on the Core StepResult
    assert not hasattr(step_result, "artifacts")


def test_agent_decision_is_a_machine_verdict_not_the_human_gate() -> None:
    decision = AgentDecision(
        verdict=AgentVerdict.REQUEST_CHANGES,
        by_role=AgentRole.REVIEWER,
        rationale="missing tests",
    )
    data = decision.to_dict()
    assert data["verdict"] == "request_changes"
    assert data["by_role"] == "reviewer"
    assert data["rationale"] == "missing tests"


def test_handoff_serializes_nested_artifacts_and_roles() -> None:
    handoff = AgentHandoff(
        from_role=AgentRole.DEVELOPER,
        to_role=AgentRole.REVIEWER,
        reason="patch ready",
        artifacts=(
            AgentArtifact(
                kind="diff",
                title="fix",
                content="--- a\n+++ b",
                produced_by=AgentRole.DEVELOPER,
            ),
        ),
    )
    data = handoff.to_dict()
    assert data["from_role"] == "developer"
    assert data["to_role"] == "reviewer"
    artifacts = data["artifacts"]
    assert isinstance(artifacts, list)
    first = artifacts[0]
    assert isinstance(first, dict)
    assert first["kind"] == "diff"  # nested model serialized recursively
    assert first["produced_by"] == "developer"  # nested enum -> value


def test_agent_protocol_is_structurally_satisfiable() -> None:
    class _FakeQaAgent:
        @property
        def role(self) -> AgentRole:
            return AgentRole.QA

        def handle(self, request: AgentRequest) -> AgentResult:
            return AgentResult(ok=True, output=f"handled {request.intent}")

    agent = _FakeQaAgent()
    assert isinstance(agent, Agent)  # runtime_checkable structural conformance
    out = agent.handle(AgentRequest(role=AgentRole.QA, intent="sweep", tenant=_tenant()))
    assert out.ok is True
    assert out.output == "handled sweep"
