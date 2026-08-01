"""Full pipeline E2E: a trigger runs a Foreman-planned, capability-routed agent mission on the Core.

trigger -> TriggerSource.normalize -> correlate -> MissionIntake -> a quality_review mission whose
steps route by capability (testing -> QA, review -> Reviewer) through the one Tool path — the
executor resolves each step to an AgentTool. Proves the dev-team spine end to end, in-memory,
and that a recurrence after closure opens a new mission (the correlation deactivator freed the ref).
"""

from __future__ import annotations

from devteam_ci import PackageResult
from devteam_intake import CIFailureSource
from devteam_runtime.intake_runtime import DevIntakeRuntime


def _green() -> list[PackageResult]:
    return [
        PackageResult("event-bus", 0, "35 passed"),
        PackageResult("tool-registry", 0, "27 passed"),
    ]


def test_a_ci_trigger_runs_a_full_agent_quality_review_mission() -> None:
    runtime = DevIntakeRuntime(_green)
    outcome = runtime.submit({"pipeline": "api"}, CIFailureSource())
    assert outcome.action == "created"
    # QA (testing) then Reviewer (review) both ran as real agent steps on the frozen Core.
    assert runtime.audit.event_names_for(outcome.mission_id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.step_completed",
        "mission.completed",
    ]


def test_a_recurrence_after_closure_opens_a_new_mission() -> None:
    runtime = DevIntakeRuntime(_green)
    first = runtime.submit({"pipeline": "api"}, CIFailureSource())
    second = runtime.submit({"pipeline": "api"}, CIFailureSource())
    # The first mission completed instantly, so the deactivator freed the ref -> a fresh mission.
    assert second.action == "created"
    assert first.mission_id != second.mission_id
