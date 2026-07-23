"""Test #3 — the Mission Catalog builds a correct `Plan` from a Mission type + inputs."""

from __future__ import annotations

import pytest
from assistant_runtime import MissionCatalog, UnknownMissionType
from mission_engine import ExecutionProfile, MissionStatus
from pipeline_contracts import TenantContext


def test_simple_question_builds_a_single_step_plan(
    mission_catalog: MissionCatalog, tenant: TenantContext
) -> None:
    goal, plan = mission_catalog.build("simple_question", {"request": "what is MFA?"}, tenant)
    assert goal == "what is MFA?"
    assert len(plan.steps) == 1
    assert plan.execution_profile is ExecutionProfile.SIMPLE  # one read-only step


def test_vendor_assessment_builds_a_composite_plan(
    mission_catalog: MissionCatalog, tenant: TenantContext
) -> None:
    goal, plan = mission_catalog.build("vendor_risk_assessment", {"request": "Acme"}, tenant)
    assert "Acme" in goal
    assert [s.description for s in plan.steps] == ["collect evidence", "analyze", "score", "report"]
    assert plan.execution_profile is ExecutionProfile.COMPOSITE


def test_the_built_plan_is_drivable_by_the_engine(
    mission_catalog: MissionCatalog, tenant: TenantContext
) -> None:
    """A correct Plan is one the frozen engine actually accepts: build it, drive it in-memory, and
    it completes with one recorded step per plan step."""
    from mission_engine import EchoExecutor, InMemoryMissionStore, MissionEngine

    goal, plan = mission_catalog.build("vendor_risk_assessment", {"request": "Acme"}, tenant)
    engine = MissionEngine(InMemoryMissionStore(), EchoExecutor())
    mission = engine.create(goal, tenant)
    engine.plan(mission, plan)
    engine.execute(mission)
    assert mission.status is MissionStatus.COMPLETED
    assert len(mission.step_results) == 4


def test_unknown_mission_type_fails_loud(
    mission_catalog: MissionCatalog, tenant: TenantContext
) -> None:
    with pytest.raises(UnknownMissionType, match="nope"):
        mission_catalog.build("nope", {}, tenant)
