"""The Mission aggregate (ADR 0042 §1): tenant bound at creation and immutable, transitions
enforced, terminal missions frozen, cross-tenant access denied."""

import pytest
from mission_engine.errors import IllegalTransition, MissionError, TenantMismatch
from mission_engine.lifecycle import MissionStatus
from mission_engine.mission import Mission
from mission_engine.plan import PlanStep, single_step_plan
from mission_engine.ports import StepResult


def _make(tenant) -> Mission:
    return Mission.create(goal="assess MFA coverage", tenant=tenant)


def test_create_binds_tenant_and_mints_identity(tenant):
    mission = _make(tenant)
    assert mission.status is MissionStatus.CREATED
    assert mission.tenant_id == tenant.tenant_id
    assert mission.id.startswith("mis_")
    assert mission.trace_id.startswith("trc_")
    assert mission.execution_profile is None  # no plan yet


def test_tenant_is_required_at_construction():
    with pytest.raises(TypeError):
        Mission.create(goal="g")  # type: ignore[call-arg]


def test_happy_path_transitions(tenant):
    mission = _make(tenant)
    mission.set_plan(single_step_plan("x"))
    assert mission.status is MissionStatus.PLANNED
    assert mission.plan_version == 1
    assert mission.execution_profile.value == "simple"

    mission.begin_execution()
    assert mission.status is MissionStatus.EXECUTING

    mission.record_step(StepResult(step_id="stp_1"))
    mission.complete()
    assert mission.status is MissionStatus.COMPLETED


def test_cannot_execute_without_a_plan(tenant):
    # A plan-less CREATED mission cannot execute — the guard fires before any transition.
    with pytest.raises(MissionError):
        _make(tenant).begin_execution()


def test_steps_cannot_be_recorded_before_executing(tenant):
    with pytest.raises(IllegalTransition):
        _make(tenant).record_step(StepResult(step_id="stp_1"))


def test_completed_mission_is_immutable(tenant):
    mission = _make(tenant)
    mission.set_plan(single_step_plan("x"))
    mission.begin_execution()
    mission.complete()
    with pytest.raises(IllegalTransition):
        mission.record_step(StepResult(step_id="stp_1"))
    with pytest.raises(IllegalTransition):
        mission.complete()


def test_tenant_cannot_be_crossed(tenant, other_tenant):
    mission = _make(tenant)
    mission.assert_tenant(tenant)  # same tenant is fine
    with pytest.raises(TenantMismatch):
        mission.assert_tenant(other_tenant)


def test_replan_is_only_legal_after_a_gate(tenant):
    mission = _make(tenant)
    mission.set_plan(single_step_plan("x"))
    with pytest.raises(IllegalTransition):
        mission.replan((PlanStep(instruction="y"),))


def test_replan_creates_a_new_version_on_the_same_mission(tenant):
    mission = _make(tenant)
    mission.set_plan(single_step_plan("x"))
    mission.begin_execution()
    mission.await_approval()
    mission.resume()
    mission.replan((PlanStep(instruction="a"), PlanStep(instruction="b")))
    assert mission.status is MissionStatus.PLANNED
    assert mission.plan_version == 2
    assert len(mission.plan_versions) == 2
    assert mission.execution_profile.value == "composite"


def test_to_dict_is_a_faithful_snapshot(tenant):
    mission = _make(tenant)
    mission.set_plan(single_step_plan("x"))
    data = mission.to_dict()
    assert data["status"] == "planned"
    assert data["tenant"]["tenant_id"] == tenant.tenant_id
    assert data["execution_profile"] == "simple"
    assert data["plan"]["version"] == 1
    assert data["step_results"] == []
