"""ADR 0051: the engine threads each step's completed predecessors into the next `StepRequest`, so
a step runs *from* the results before it. Additive and transient — no persistence change."""

from __future__ import annotations

from event_bus.bus import RecordingEventBus
from mission_engine import (
    InMemoryMissionStore,
    MissionEngine,
    MissionStatus,
    Plan,
    PlanStep,
    StepRequest,
    StepResult,
)
from pipeline_contracts import TenantContext


class _RecordingExecutor:
    """Records the `prior_results` each step was handed, and returns a per-step output."""

    def __init__(self) -> None:
        self.prior_per_step: list[tuple[str, ...]] = []

    def execute(self, request: StepRequest) -> StepResult:
        self.prior_per_step.append(tuple(r.output for r in request.prior_results))
        return StepResult(step_id=request.step_id, ok=True, output=f"out:{request.instruction}")


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u1")


def test_each_step_receives_the_results_of_all_prior_steps() -> None:
    executor = _RecordingExecutor()
    engine = MissionEngine(InMemoryMissionStore(), executor, events=RecordingEventBus())
    tenant = _tenant()
    mission = engine.create("composite", tenant)
    engine.plan(
        mission,
        Plan(steps=(
            PlanStep(description="a", instruction="one"),
            PlanStep(description="b", instruction="two"),
            PlanStep(description="c", instruction="three"),
        )),
    )
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    # step 1 sees nothing; step 2 sees step 1's output; step 3 sees steps 1 and 2's outputs.
    assert executor.prior_per_step == [
        (),
        ("out:one",),
        ("out:one", "out:two"),
    ]


def test_a_single_step_mission_gets_no_prior_results() -> None:
    executor = _RecordingExecutor()
    engine = MissionEngine(InMemoryMissionStore(), executor, events=RecordingEventBus())
    mission = engine.run_simple("solo", _tenant(), "only")
    assert mission.status is MissionStatus.COMPLETED
    assert executor.prior_per_step == [()]   # first/only step has no predecessors
