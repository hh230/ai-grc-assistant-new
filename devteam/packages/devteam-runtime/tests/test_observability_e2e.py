"""End-to-end: the observability layer captures a REAL composite mission, changing nothing.

Drives the actual read-only quality-review mission (QA -> Reviewer) on the frozen MissionEngine
with the REAL agents, but with a ``DevTeamObservability`` injected. Proves two things at once: the
mission runs exactly as before (same status, same step results — zero change to any agent), and the
observability view now shows the live agents, the explicit QA -> Reviewer relay, and the immutable
session records.
"""

from __future__ import annotations

from devteam_ci import PackageResult
from devteam_observability import DevTeamObservability, agent_id_for
from devteam_observability.adapter import ORG_ROSTER, PLATFORM_ROSTER
from devteam_protocol import AgentRole
from devteam_runtime.agent_runtime import AgentMissionRuntime
from mission_engine.lifecycle import MissionStatus


def _green() -> list[PackageResult]:
    return [
        PackageResult("event-bus", 0, "35 passed"),
        PackageResult("tool-registry", 0, "27 passed"),
    ]


def _agent_key(dto: dict[str, object]) -> str:
    """Pull the flat agent key out of a view DTO (narrows the JSON ``object`` for mypy)."""
    agent = dto["agent"]
    assert isinstance(agent, dict)
    return str(agent["key"])


def test_observability_captures_the_real_composite_mission_without_changing_it() -> None:
    obs = DevTeamObservability()
    runtime = AgentMissionRuntime(_green, observability=obs)

    mission = runtime.run_quality_review()

    # (1) The mission is UNCHANGED by observation — same behavior as the un-observed runtime.
    assert mission.status is MissionStatus.COMPLETED
    assert len(mission.step_results) == 2
    assert "suites green" in mission.step_results[0].output
    assert "Reviewer:" in mission.step_results[1].output

    # (2) The view now shows the live team.
    view = obs.view
    agents = {_agent_key(a): a for a in view.agents()}
    # The whole platform roster is seeded (engineering squad + AI Organization), not only the actors.
    assert len(agents) == len(PLATFORM_ROSTER) + len(ORG_ROSTER)
    assert agents["platform:qa"]["executions"] == 1
    assert agents["platform:qa"]["status"] == "idle"
    assert agents["platform:reviewer"]["executions"] == 1

    # (3) Ownership + the real QA -> Reviewer relay, from explicit events (not inferred).
    assert view.ownership() == {mission.id: "platform:qa"}
    flow = view.mission_flow(mission.id)
    assert flow is not None
    handoff_list = flow["handoffs"]
    assert isinstance(handoff_list, list)
    assert [(h["from"]["key"], h["to"]["key"]) for h in handoff_list] == [
        ("platform:qa", "platform:reviewer")
    ]

    # (4) Two immutable session records — the execution timeline (QA then Reviewer).
    sessions = view.mission_sessions(mission.id)
    assert [_agent_key(s) for s in sessions] == ["platform:qa", "platform:reviewer"]
    assert all(s["status"] == "completed" for s in sessions)


def test_the_reviewers_verdict_is_captured_in_its_decision_history() -> None:
    obs = DevTeamObservability()
    runtime = AgentMissionRuntime(_green, observability=obs)
    runtime.run_quality_review()

    reviewer = obs.view.agent(agent_id_for(AgentRole.REVIEWER))
    assert reviewer is not None
    history = reviewer["decision_history"]
    assert isinstance(history, list)
    assert len(history) == 1  # the Reviewer reached a verdict, captured with zero agent change
