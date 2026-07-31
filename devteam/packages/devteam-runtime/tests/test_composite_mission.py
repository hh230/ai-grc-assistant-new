from __future__ import annotations

from devteam_ci import PackageResult
from devteam_contracts import PLATFORM_TENANT_ID
from devteam_runtime.agent_runtime import AgentMissionRuntime
from mission_engine.lifecycle import MissionStatus


def _green() -> list[PackageResult]:
    return [
        PackageResult("event-bus", 0, "35 passed"),
        PackageResult("tool-registry", 0, "27 passed"),
    ]


def _one_fail() -> list[PackageResult]:
    return [PackageResult("a", 0, "3 passed"), PackageResult("b", 1, "1 failed")]


def test_composite_capability_routed_mission_runs_on_the_frozen_core() -> None:
    runtime = AgentMissionRuntime(_green)
    mission = runtime.run_quality_review()

    assert mission.status is MissionStatus.COMPLETED
    assert mission.tenant_id == PLATFORM_TENANT_ID
    assert len(mission.step_results) == 2  # testing + review, routed by capability
    assert "suites green" in mission.step_results[0].output  # testing (QA) ran
    assert "Reviewer:" in mission.step_results[1].output  # review read testing's output


def test_audit_records_the_full_composite_event_stream() -> None:
    runtime = AgentMissionRuntime(_green)
    mission = runtime.run_quality_review()
    assert runtime.audit.event_names_for(mission.id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",  # testing
        "mission.step_completed",  # review
        "mission.completed",
    ]


def test_review_reads_testing_output_across_the_handoff() -> None:
    # Testing reports a shortfall; review reads the handoff (ADR 0051) and requests changes.
    runtime = AgentMissionRuntime(_one_fail)
    mission = runtime.run_quality_review()
    # Read-only agents complete the mission; the verdict reports the shortfall (no abort).
    assert mission.status is MissionStatus.COMPLETED
    assert "request_changes" in mission.step_results[1].output.lower()
