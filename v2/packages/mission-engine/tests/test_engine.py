"""End-to-end engine behaviour (ADR 0042 §2): the happy path completes and is fully governed,
the human gate pauses fail-safe, failures fail-safe, reads are tenant-scoped, and creation is
idempotent. The engine is driven through the real reference adapters, not mocks."""

import pytest
from mission_engine import (
    InMemoryMissionStore,
    MissionEngine,
    MissionNotFound,
    MissionStatus,
    Plan,
    PlanStep,
    StepResult,
)


def _names(bus) -> list[str]:
    return [event.name for event in bus.events]


def test_run_simple_completes_end_to_end(engine, bus, tenant):
    mission = engine.run_simple("assess MFA", tenant, "what does NCA ECC say about MFA?")

    assert mission.status is MissionStatus.COMPLETED
    assert mission.execution_profile.value == "simple"
    assert len(mission.step_results) == 1
    assert mission.step_results[0].output.startswith("echo:")
    assert _names(bus) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.completed",
    ]


def test_every_emitted_event_is_stamped_for_this_mission(engine, bus, tenant):
    mission = engine.run_simple("q", tenant, "x")
    for event in bus.events:
        assert event.mission_id == mission.id
        assert event.tenant_id == tenant.tenant_id
        assert event.trace_id == mission.trace_id


def test_mission_is_persisted_and_retrievable_within_its_tenant(engine, tenant):
    mission = engine.run_simple("q", tenant, "x")
    fetched = engine.get(mission.id, tenant)
    assert fetched.id == mission.id
    assert fetched.status is MissionStatus.COMPLETED


def test_get_is_tenant_scoped(engine, tenant, other_tenant):
    mission = engine.run_simple("q", tenant, "x")
    with pytest.raises(MissionNotFound):
        engine.get(mission.id, other_tenant)


def test_create_is_idempotent_per_tenant(engine, tenant):
    first = engine.create("q", tenant, idempotency_key="k")
    second = engine.create("q", tenant, idempotency_key="k")
    assert first.id == second.id


def test_run_simple_is_idempotent_and_does_not_re_run(engine, bus, tenant):
    first = engine.run_simple("q", tenant, "x", idempotency_key="k")
    event_count = len(bus.events)
    second = engine.run_simple("q", tenant, "x", idempotency_key="k")
    assert first.id == second.id
    assert second.status is MissionStatus.COMPLETED
    assert len(bus.events) == event_count  # the second call short-circuits, emitting nothing


def test_composite_and_simple_share_one_execution_path(engine, bus, tenant):
    # [criterion 4] execution_profile drives NO control flow: a composite (multi read-only
    # step) plan runs through the identical create → plan → execute path a simple one does,
    # completing and emitting one step_completed per step. There is no separate lane.
    mission = engine.create("multi-step read", tenant)
    engine.plan(
        mission,
        Plan(
            steps=(
                PlanStep(instruction="a"),
                PlanStep(instruction="b"),
                PlanStep(instruction="c"),
            )
        ),
    )
    engine.execute(mission)

    assert mission.execution_profile.value == "composite"
    assert mission.status is MissionStatus.COMPLETED
    assert len(mission.step_results) == 3
    assert _names(bus).count("mission.step_completed") == 3


def test_execution_profile_is_read_only_and_derived(tenant):
    # [criterion 4] the profile is a derived property with no setter — it can never diverge
    # from the plan or be forced to a value, so it cannot become independent state.
    from mission_engine import Mission

    mission = Mission.create(goal="g", tenant=tenant)
    with pytest.raises(AttributeError):
        mission.execution_profile = "simple"  # type: ignore[misc]


def test_consequential_step_pauses_at_the_human_gate(engine, bus, tenant):
    mission = engine.create("draft policy", tenant)
    engine.plan(mission, Plan(steps=(PlanStep(instruction="write", consequential=True),)))
    engine.execute(mission)

    assert mission.status is MissionStatus.AWAITING_APPROVAL
    assert mission.step_results == []  # nothing ran before the gate — fail-safe
    assert "mission.awaiting_approval" in _names(bus)
    assert "mission.completed" not in _names(bus)


def test_executor_exception_fails_the_mission_safe(store, bus, tenant):
    class Boom:
        def execute(self, request):
            raise RuntimeError("kaboom")

    engine = MissionEngine(store, Boom(), events=bus)
    mission = engine.run_simple("q", tenant, "x")
    assert mission.status is MissionStatus.FAILED
    assert "mission.failed" in _names(bus)


def test_not_ok_step_result_fails_the_mission_safe(store, bus, tenant):
    class NotOk:
        def execute(self, request):
            return StepResult(step_id=request.step_id, ok=False)

    engine = MissionEngine(store, NotOk(), events=bus)
    mission = engine.run_simple("q", tenant, "x")
    assert mission.status is MissionStatus.FAILED


def test_engine_runs_without_a_bus_wired(tenant):
    from mission_engine import EchoExecutor

    engine = MissionEngine(InMemoryMissionStore(), EchoExecutor())  # events=None
    mission = engine.run_simple("q", tenant, "x")
    assert mission.status is MissionStatus.COMPLETED


def test_cancel_stops_the_mission_fail_safe(engine, bus, tenant):
    mission = engine.create("q", tenant)
    engine.cancel(mission, reason="user aborted")
    assert mission.status is MissionStatus.CANCELLED
    assert "mission.cancelled" in _names(bus)
