"""The mission-bound observation point: events around a step, explicit handoffs, session sealing."""

from __future__ import annotations

from collections.abc import Callable

from devteam_observability import (
    AgentHandoffOccurred,
    AgentRuntimeRegistry,
    AgentStatus,
    HandoffSource,
    ObservingExecutor,
    ResultCourier,
    StepCapture,
    agent_id_for,
)
from devteam_protocol import (
    AgentArtifact,
    AgentCapability,
    AgentDecision,
    AgentHandoff,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
)
from mission_engine.ports import StepRequest, StepResult
from pipeline_contracts import TenantContext


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="platform", principal_id="foreman")


def _counter(values: list[float]) -> Callable[[], float]:
    it = iter(values)
    return lambda: next(it)


class _FakeAgent:
    """A minimal devteam agent (role + handle) — proves the courier/executor need no real agent."""

    def __init__(
        self,
        role: AgentRole,
        *,
        decision: AgentDecision | None = None,
        artifacts: tuple[AgentArtifact, ...] = (),
        handoff: AgentHandoff | None = None,
        output: str = "done",
        ok: bool = True,
    ) -> None:
        self._role = role
        self._result = AgentResult(
            ok=ok, output=output, decision=decision, artifacts=artifacts, handoff=handoff
        )

    @property
    def role(self) -> AgentRole:
        return self._role

    def handle(self, request: AgentRequest) -> AgentResult:
        return self._result


class _InnerViaCourier:
    """Mimics DevToolExecutor + AgentTool for one couriered agent: run it, fold to a StepResult."""

    def __init__(self, courier: ResultCourier) -> None:
        self._courier = courier

    def execute(self, request: StepRequest) -> StepResult:
        result = self._courier.handle(
            AgentRequest(role=self._courier.role, intent=request.instruction, tenant=request.tenant)
        )
        return StepResult(step_id=request.step_id, ok=result.ok, output=result.output)


class _RoutingInner:
    """Resolve a step's tool to one of several couriered agents — for multi-step relay tests."""

    def __init__(self, couriers: dict[str, ResultCourier]) -> None:
        self._couriers = couriers

    def execute(self, request: StepRequest) -> StepResult:
        courier = self._couriers[request.tool]
        result = courier.handle(
            AgentRequest(role=courier.role, intent=request.instruction, tenant=request.tenant)
        )
        return StepResult(step_id=request.step_id, ok=result.ok, output=result.output)


class _EchoInner:
    def execute(self, request: StepRequest) -> StepResult:
        return StepResult(step_id=request.step_id, ok=True, output="git")


def _step(step_id: str, capability: AgentCapability) -> StepRequest:
    return StepRequest(
        mission_id="m1",
        step_id=step_id,
        tenant=_tenant(),
        instruction=capability.value,
        tool=capability.value,
    )


def _handoffs(registry: AgentRuntimeRegistry) -> list[AgentHandoffOccurred]:
    return [e for e in registry.recent_events() if isinstance(e, AgentHandoffOccurred)]


def test_agent_step_emits_started_decision_completed_with_mission_context() -> None:
    capture = StepCapture()
    registry = AgentRuntimeRegistry()
    decision = AgentDecision(
        verdict=AgentVerdict.APPROVE, by_role=AgentRole.REVIEWER, rationale="ok"
    )
    courier = ResultCourier(_FakeAgent(AgentRole.REVIEWER, decision=decision), capture)
    executor = ObservingExecutor(_InnerViaCourier(courier), registry, capture)

    result = executor.execute(_step("s1", AgentCapability.REVIEW))

    assert result.output == "done"  # the inner result is passed through unchanged
    kinds = [event.to_dict()["kind"] for event in registry.recent_events()]
    assert "AgentStarted" in kinds
    assert "AgentDecisionRecorded" in kinds
    assert "AgentCompleted" in kinds
    # Every emitted event carries the mission id the tool boundary would have dropped.
    assert all(event.mission_id == "m1" for event in registry.recent_events())
    reviewer = registry.state_for(agent_id_for(AgentRole.REVIEWER))
    assert reviewer is not None
    assert reviewer.status is AgentStatus.IDLE
    assert reviewer.decision_history[0].verdict == "approve"


def test_a_blocking_verdict_leaves_the_agent_blocked() -> None:
    capture = StepCapture()
    registry = AgentRuntimeRegistry()
    decision = AgentDecision(verdict=AgentVerdict.BLOCK, by_role=AgentRole.REVIEWER, rationale="no")
    courier = ResultCourier(_FakeAgent(AgentRole.REVIEWER, decision=decision), capture)
    executor = ObservingExecutor(_InnerViaCourier(courier), registry, capture)

    executor.execute(_step("s1", AgentCapability.REVIEW))

    reviewer = registry.state_for(agent_id_for(AgentRole.REVIEWER))
    assert reviewer is not None
    assert reviewer.status is AgentStatus.BLOCKED


def test_duration_is_measured_from_the_monotonic_clock() -> None:
    capture = StepCapture()
    registry = AgentRuntimeRegistry()
    courier = ResultCourier(_FakeAgent(AgentRole.QA), capture)
    executor = ObservingExecutor(
        _InnerViaCourier(courier),
        registry,
        capture,
        monotonic=_counter([0.0, 0.25]),  # start, end -> 250ms
        wall=lambda: 7.0,
    )
    executor.execute(_step("s1", AgentCapability.TESTING))
    qa = registry.state_for(agent_id_for(AgentRole.QA))
    assert qa is not None
    assert qa.average_duration_ms == 250.0


def test_relay_between_two_agents_emits_an_observed_handoff() -> None:
    capture = StepCapture()
    registry = AgentRuntimeRegistry()
    couriers = {
        AgentCapability.TESTING.value: ResultCourier(_FakeAgent(AgentRole.QA), capture),
        AgentCapability.REVIEW.value: ResultCourier(_FakeAgent(AgentRole.REVIEWER), capture),
    }
    executor = ObservingExecutor(_RoutingInner(couriers), registry, capture)

    executor.execute(_step("s1", AgentCapability.TESTING))
    executor.execute(_step("s2", AgentCapability.REVIEW))

    handoffs = _handoffs(registry)
    assert len(handoffs) == 1
    assert handoffs[0].source is HandoffSource.OBSERVED
    assert handoffs[0].from_agent == agent_id_for(AgentRole.QA)
    assert handoffs[0].to_agent == agent_id_for(AgentRole.REVIEWER)


def test_a_declared_handoff_is_preferred_over_an_observed_one() -> None:
    capture = StepCapture()
    registry = AgentRuntimeRegistry()
    declared = AgentHandoff(
        from_role=AgentRole.QA, to_role=AgentRole.REVIEWER, reason="please review the run"
    )
    couriers = {
        AgentCapability.TESTING.value: ResultCourier(
            _FakeAgent(AgentRole.QA, handoff=declared), capture
        ),
        AgentCapability.REVIEW.value: ResultCourier(_FakeAgent(AgentRole.REVIEWER), capture),
    }
    executor = ObservingExecutor(_RoutingInner(couriers), registry, capture)

    executor.execute(_step("s1", AgentCapability.TESTING))
    executor.execute(_step("s2", AgentCapability.REVIEW))

    handoffs = _handoffs(registry)
    assert len(handoffs) == 1
    assert handoffs[0].source is HandoffSource.DECLARED
    assert handoffs[0].reason == "please review the run"


def test_completed_session_captures_output_and_artifacts() -> None:
    capture = StepCapture()
    registry = AgentRuntimeRegistry()
    agent = _FakeAgent(
        AgentRole.DEVELOPER,
        artifacts=(AgentArtifact(kind="diff", title="fix.patch"),),
        output="a wall of developer output " * 40,
    )
    executor = ObservingExecutor(_InnerViaCourier(ResultCourier(agent, capture)), registry, capture)

    executor.execute(_step("s1", AgentCapability.IMPLEMENTATION))

    sealed = registry.completed_sessions()[0]
    assert sealed.artifacts[0].kind == "diff"
    assert sealed.artifacts[0].title == "fix.patch"
    assert sealed.output_summary.endswith("…")  # truncated
    assert len(sealed.output_summary) <= 240


def test_non_agent_step_passes_through_without_events() -> None:
    registry = AgentRuntimeRegistry()
    executor = ObservingExecutor(_EchoInner(), registry, StepCapture())
    request = StepRequest(
        mission_id="m1", step_id="s2", tenant=_tenant(), instruction="", tool="apply_patch"
    )
    result = executor.execute(request)
    assert result.output == "git"
    assert registry.recent_events() == []


def test_courier_returns_the_agents_result_unchanged() -> None:
    capture = StepCapture()
    agent = _FakeAgent(AgentRole.QA)
    courier = ResultCourier(agent, capture)
    result = courier.handle(AgentRequest(role=AgentRole.QA, intent="x", tenant=_tenant()))
    assert result.output == "done"
    assert result.ok is True
