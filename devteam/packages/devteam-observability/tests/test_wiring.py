"""End-to-end wiring: a two-agent mission observed through DevTeamObservability.

Drives a QA -> Reviewer quality-review shaped mission through the SAME wrappers a composition root
applies (courier the agents, wrap the executor, subscribe the bridge), using a fake inner executor
that mimics DevToolExecutor + AgentTool. The real MissionEngine E2E lands in devteam-runtime, where
the real executor and agents live; here we prove the adapter turns runtime activity into the view a
dashboard reads — with zero change to any agent.
"""

from __future__ import annotations

import json

from devteam_observability import AgentStatus, DevTeamObservability, agent_id_for
from devteam_observability.adapter import ORG_ROSTER, PLATFORM_ROSTER
from devteam_protocol import (
    Agent,
    AgentCapability,
    AgentDecision,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
)
from event_bus import InProcessEventBus
from mission_engine.events import MissionCompleted, MissionCreated, MissionStepCompleted
from mission_engine.ports import StepRequest, StepResult
from pipeline_contracts import TenantContext


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="platform", principal_id="foreman")


class _FakeAgent:
    def __init__(self, role: AgentRole, decision: AgentDecision | None = None) -> None:
        self._role = role
        self._decision = decision

    @property
    def role(self) -> AgentRole:
        return self._role

    def handle(self, request: AgentRequest) -> AgentResult:
        return AgentResult(ok=True, output=f"{self._role.value} done", decision=self._decision)


class _FakeInner:
    """Resolve a step's tool to the couriered agent and run it, folding to a StepResult — the same
    shape DevToolExecutor + AgentTool produce."""

    def __init__(self, agents_by_tool: dict[str, Agent]) -> None:
        self._agents = agents_by_tool

    def execute(self, request: StepRequest) -> StepResult:
        agent = self._agents[request.tool]
        result = agent.handle(
            AgentRequest(role=agent.role, intent=request.instruction, tenant=request.tenant)
        )
        return StepResult(step_id=request.step_id, ok=result.ok, output=result.output)


def _step(step_id: str, tool: AgentCapability) -> StepRequest:
    return StepRequest(
        mission_id="m1", step_id=step_id, tenant=_tenant(), instruction=tool.value, tool=tool.value
    )


def _run_quality_review() -> DevTeamObservability:
    obs = DevTeamObservability()
    review_decision = AgentDecision(verdict=AgentVerdict.APPROVE, by_role=AgentRole.REVIEWER)
    couriered = obs.observe_agents(
        {
            AgentCapability.TESTING: _FakeAgent(AgentRole.QA),
            AgentCapability.REVIEW: _FakeAgent(AgentRole.REVIEWER, review_decision),
        }
    )
    inner = _FakeInner({cap.value: agent for cap, agent in couriered.items()})
    executor = obs.observe_executor(inner)

    bus = InProcessEventBus()
    obs.subscribe(bus)

    # Drive the mission the way the engine would: created -> step -> step -> completed.
    bus.publish(MissionCreated(trace_id="t", tenant_id="platform", mission_id="m1", goal="review"))
    executor.execute(_step("s1", AgentCapability.TESTING))
    bus.publish(
        MissionStepCompleted(trace_id="t", tenant_id="platform", mission_id="m1", step_id="s1")
    )
    executor.execute(_step("s2", AgentCapability.REVIEW))
    bus.publish(
        MissionStepCompleted(trace_id="t", tenant_id="platform", mission_id="m1", step_id="s2")
    )
    bus.publish(
        MissionCompleted(trace_id="t", tenant_id="platform", mission_id="m1", step_count=2)
    )
    return obs


def test_whole_team_is_visible_and_the_two_actors_completed_the_mission() -> None:
    view = _run_quality_review().view
    agents = {a["agent"]["key"]: a for a in view.agents()}  # type: ignore[index]
    # The whole platform roster is seeded, not only the two that acted.
    assert len(agents) == len(PLATFORM_ROSTER) + len(ORG_ROSTER)
    assert agents["platform:qa"]["status"] == AgentStatus.IDLE.value
    assert agents["platform:qa"]["completed_missions"] == 1
    assert agents["platform:reviewer"]["completed_missions"] == 1


def test_the_relay_and_ownership_are_observable() -> None:
    view = _run_quality_review().view
    assert view.ownership() == {"m1": "platform:qa"}  # QA ran first, so it owns the mission
    flow = view.mission_flow("m1")
    assert flow is not None
    assert flow["status"] == "completed"
    assert flow["handoffs"] == [
        {
            "from": agent_id_for(AgentRole.QA).to_dict(),
            "to": agent_id_for(AgentRole.REVIEWER).to_dict(),
        }
    ]


def test_reviewers_decision_is_in_its_history() -> None:
    view = _run_quality_review().view
    reviewer = view.agent(agent_id_for(AgentRole.REVIEWER))
    assert reviewer is not None
    history = reviewer["decision_history"]
    assert isinstance(history, list)
    assert history[0]["verdict"] == "approve"


def test_snapshot_serializes_whole() -> None:
    json.dumps(_run_quality_review().view.snapshot())
