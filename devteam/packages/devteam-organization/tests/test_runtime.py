"""The OrganizationRuntime — a governed mission driven through the org and observed end to end."""

from __future__ import annotations

from devteam_organization import OrganizationRuntime
from mission_engine.lifecycle import MissionStatus

# A goal that raises every signal, so the mission runs the full CEO→CTO→CISO→GRC→QA→DevTeam chain.
_FULL_GOAL = "Implement encryption and map ISO 27001 controls, with tests"
_EXPECTED_CHAIN = [
    "platform:ceo",
    "platform:cto",
    "platform:ciso",
    "platform:grc_expert",
    "platform:qa",
    "platform:devteam",
]


def _keys(sessions: list[dict[str, object]]) -> list[str]:
    keys: list[str] = []
    for session in sessions:
        agent = session.get("agent")
        if isinstance(agent, dict) and isinstance(agent.get("key"), str):
            keys.append(str(agent["key"]))
    return keys


def test_a_mission_flows_through_the_whole_organization(runtime: OrganizationRuntime) -> None:
    mission = runtime.run_mission(_FULL_GOAL)
    assert mission.status is MissionStatus.COMPLETED

    sessions = runtime.view.mission_sessions(mission.id)
    assert _keys(sessions) == _EXPECTED_CHAIN  # CEO leads, DevTeam closes, in order


def test_every_stage_records_a_decision(runtime: OrganizationRuntime) -> None:
    mission = runtime.run_mission(_FULL_GOAL)
    sessions = runtime.view.mission_sessions(mission.id)
    assert all(session.get("decision") is not None for session in sessions)


def test_the_handoff_chain_and_ownership_are_observable(runtime: OrganizationRuntime) -> None:
    mission = runtime.run_mission(_FULL_GOAL)
    flow = runtime.view.mission_flow(mission.id)
    assert flow is not None
    assert flow["status"] == "completed"
    handoffs = flow["handoffs"]
    assert isinstance(handoffs, list) and len(handoffs) == 5  # CEO→CTO→…→DevTeam
    assert runtime.view.ownership()[mission.id] == "platform:ceo"


def test_the_whole_platform_roster_is_visible(runtime: OrganizationRuntime) -> None:
    runtime.run_mission(_FULL_GOAL)
    keys = {
        str(dto["agent"]["key"])  # type: ignore[index]
        for dto in runtime.view.agents()
    }
    # The AI Organization…
    assert {
        "platform:ceo",
        "platform:cto",
        "platform:ciso",
        "platform:grc_expert",
        "platform:devteam",
        "platform:supervisor",
    } <= keys
    # …alongside the engineering squad (nothing removed).
    assert {"platform:foreman", "platform:qa", "platform:developer"} <= keys


def test_the_mission_is_audited_as_a_governed_lifecycle(runtime: OrganizationRuntime) -> None:
    mission = runtime.run_mission(_FULL_GOAL)
    names = runtime.audit.event_names_for(mission.id)
    assert names[0] == "mission.created"
    assert names[-1] == "mission.completed"
    assert names.count("mission.step_completed") == 6  # one per stage


def test_a_scoped_mission_runs_only_its_stages(runtime: OrganizationRuntime) -> None:
    mission = runtime.run_mission("Draft a GDPR data-retention policy")
    assert mission.status is MissionStatus.COMPLETED
    # CEO → GRC Expert → DevTeam only (CTO/CISO/QA skipped by the planner).
    assert _keys(runtime.view.mission_sessions(mission.id)) == [
        "platform:ceo",
        "platform:grc_expert",
        "platform:devteam",
    ]


def test_health_check_runs_the_supervisor_as_an_observed_mission(
    runtime: OrganizationRuntime,
) -> None:
    mission = runtime.run_health_check()
    assert mission.status is MissionStatus.COMPLETED
    sessions = runtime.view.mission_sessions(mission.id)
    assert _keys(sessions) == ["platform:supervisor"]
    assert sessions[0].get("decision") is not None  # a real healthy/escalate verdict
