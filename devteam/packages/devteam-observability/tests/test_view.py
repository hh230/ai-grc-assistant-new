"""The read API: JSON-ready DTOs, ownership, and the whole-dashboard snapshot."""

from __future__ import annotations

import json

from devteam_observability import (
    AgentCompleted,
    AgentHandoffOccurred,
    AgentId,
    AgentRuntimeRegistry,
    AgentStarted,
    AgentSubsystem,
    MissionEventKind,
    MissionObserved,
    RuntimeStateView,
)


def _agent(role: str) -> AgentId:
    return AgentId(AgentSubsystem.PLATFORM, role)


QA = _agent("qa")
REVIEWER = _agent("reviewer")


def _driven_registry() -> AgentRuntimeRegistry:
    registry = AgentRuntimeRegistry()
    registry.register(QA, display_name="QA")
    registry.register(REVIEWER, display_name="Reviewer")
    registry.observe(AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0))
    registry.observe(
        AgentCompleted(mission_id="m1", agent=QA, step_id="s1", duration_ms=120.0, occurred_at=2.0)
    )
    # Explicit handoff event is the source of truth for the QA -> Reviewer relay.
    registry.observe(
        AgentHandoffOccurred(mission_id="m1", from_agent=QA, to_agent=REVIEWER, occurred_at=2.5)
    )
    registry.observe(AgentStarted(mission_id="m1", agent=REVIEWER, step_id="s2", occurred_at=3.0))
    registry.observe(AgentCompleted(mission_id="m1", agent=REVIEWER, step_id="s2", occurred_at=4.0))
    registry.observe(
        MissionObserved(mission_id="m1", kind=MissionEventKind.COMPLETED, occurred_at=5.0)
    )
    return registry


def test_agents_dto_is_sorted_and_json_serializable() -> None:
    view = RuntimeStateView(_driven_registry())
    agents = view.agents()
    keys = [agent["agent"]["key"] for agent in agents]  # type: ignore[index]
    assert keys == ["platform:qa", "platform:reviewer"]  # sorted by key
    # The whole payload must round-trip through JSON (it is what a dashboard route returns).
    json.dumps(agents)


def test_agent_dto_carries_the_live_fields() -> None:
    view = RuntimeStateView(_driven_registry())
    qa = view.agent(QA)
    assert qa is not None
    assert qa["status"] == "idle"
    assert qa["completed_missions"] == 1
    assert qa["average_duration_ms"] == 120.0
    assert qa["display_name"] == "QA"


def test_unknown_agent_reads_as_none() -> None:
    view = RuntimeStateView(AgentRuntimeRegistry())
    assert view.agent(_agent("nobody")) is None


def test_ownership_maps_mission_to_owning_agent() -> None:
    view = RuntimeStateView(_driven_registry())
    assert view.ownership() == {"m1": "platform:qa"}


def test_mission_flow_exposes_participants_handoffs_and_status() -> None:
    view = RuntimeStateView(_driven_registry())
    flow = view.mission_flow("m1")
    assert flow is not None
    assert flow["status"] == "completed"
    participants = flow["participants"]
    assert isinstance(participants, list)
    participant_keys = [p["key"] for p in participants]
    assert participant_keys == ["platform:qa", "platform:reviewer"]
    assert flow["handoffs"] == [
        {"from": QA.to_dict(), "to": REVIEWER.to_dict()},
    ]


def test_snapshot_is_one_json_payload_with_every_panel() -> None:
    view = RuntimeStateView(_driven_registry())
    snapshot = view.snapshot()
    assert set(snapshot) == {"agents", "missions", "ownership", "recent_sessions", "recent_events"}
    json.dumps(snapshot)  # a single dashboard poll must serialize whole


def test_mission_sessions_expose_the_execution_timeline() -> None:
    view = RuntimeStateView(_driven_registry())
    sessions = view.mission_sessions("m1")
    # Two sealed sessions (QA then Reviewer), oldest first — the timeline foundation.
    assert [s["step_id"] for s in sessions] == ["s1", "s2"]
    assert all(s["status"] == "completed" for s in sessions)
    assert sessions[0]["agent"]["key"] == "platform:qa"  # type: ignore[index]


def test_recent_events_feed_includes_status_transitions() -> None:
    view = RuntimeStateView(_driven_registry())
    kinds = {event["kind"] for event in view.recent_events()}
    assert "AgentStarted" in kinds
    assert "AgentStatusChanged" in kinds
    assert "AgentCompleted" in kinds
