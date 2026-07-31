"""The projection fold: status transitions, per-agent stats, sessions, and the mission index."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from devteam_observability import (
    AgentAssigned,
    AgentCompleted,
    AgentDecisionRecorded,
    AgentHandoffOccurred,
    AgentId,
    AgentPhase,
    AgentRuntimeRegistry,
    AgentStarted,
    AgentStatus,
    AgentSubsystem,
    ArtifactRef,
    MissionEventKind,
    MissionObserved,
    SessionStatus,
)


def _agent(role: str) -> AgentId:
    return AgentId(AgentSubsystem.PLATFORM, role)


DEVELOPER = _agent("developer")
REVIEWER = _agent("reviewer")
QA = _agent("qa")


def test_register_seeds_a_known_agent_as_idle() -> None:
    registry = AgentRuntimeRegistry()
    state = registry.register(QA, display_name="QA")
    assert state.status is AgentStatus.IDLE
    assert state.display_name == "QA"
    assert registry.state_for(QA) is state


def test_assigned_then_started_then_completed_walks_waiting_working_idle() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentAssigned(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0))
    assert registry.state_for(QA) is not None
    assert registry.state_for(QA).status is AgentStatus.WAITING  # type: ignore[union-attr]

    registry.observe(AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0))
    state = registry.state_for(QA)
    assert state is not None
    assert state.status is AgentStatus.WORKING
    assert state.current_mission_id == "m1"
    assert state.current_step_id == "s1"

    registry.observe(
        AgentCompleted(mission_id="m1", agent=QA, step_id="s1", duration_ms=125.0, occurred_at=3.0)
    )
    state = registry.state_for(QA)
    assert state is not None
    assert state.status is AgentStatus.IDLE
    assert state.executions == 1
    assert state.current_step_id is None
    assert state.last_activity_at == 3.0


def test_thinking_phase_is_distinguished_from_working() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(
        AgentStarted(mission_id="m1", agent=DEVELOPER, phase=AgentPhase.THINKING, occurred_at=1.0)
    )
    state = registry.state_for(DEVELOPER)
    assert state is not None
    assert state.status is AgentStatus.THINKING


def test_blocking_verdict_moves_agent_to_blocked() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=REVIEWER, occurred_at=1.0))
    registry.observe(
        AgentCompleted(mission_id="m1", agent=REVIEWER, verdict="escalate", occurred_at=2.0)
    )
    state = registry.state_for(REVIEWER)
    assert state is not None
    assert state.status is AgentStatus.BLOCKED


def test_average_duration_is_a_rolling_mean() -> None:
    registry = AgentRuntimeRegistry()
    for i, ms in enumerate((100.0, 300.0), start=1):
        registry.observe(AgentStarted(mission_id=f"m{i}", agent=QA, occurred_at=float(i)))
        registry.observe(
            AgentCompleted(mission_id=f"m{i}", agent=QA, duration_ms=ms, occurred_at=float(i) + 0.5)
        )
    state = registry.state_for(QA)
    assert state is not None
    assert state.executions == 2
    assert state.average_duration_ms == 200.0


def test_duration_falls_back_to_started_completed_span_when_unmeasured() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=QA, occurred_at=10.0))
    registry.observe(AgentCompleted(mission_id="m1", agent=QA, duration_ms=0.0, occurred_at=10.4))
    state = registry.state_for(QA)
    assert state is not None
    assert round(state.average_duration_ms) == 400  # 0.4s -> 400ms


def test_decision_history_accumulates_records() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(
        AgentDecisionRecorded(
            mission_id="m1",
            agent=REVIEWER,
            verdict="request_changes",
            rationale="missing tests",
            occurred_at=1.0,
        )
    )
    state = registry.state_for(REVIEWER)
    assert state is not None
    assert len(state.decision_history) == 1
    assert state.decision_history[0].verdict == "request_changes"
    assert state.decision_history[0].rationale == "missing tests"


def test_handoff_records_ownership_participants_and_chain() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=QA, occurred_at=1.0))
    registry.observe(
        AgentHandoffOccurred(
            mission_id="m1",
            from_agent=QA,
            to_agent=REVIEWER,
            reason="review results",
            occurred_at=2.0,
        )
    )
    mission = registry.mission_state("m1")
    assert mission is not None
    assert mission.owner == QA  # first agent seen on the mission
    assert mission.participants == [QA, REVIEWER]
    assert mission.handoffs == [(QA, REVIEWER)]


def test_registry_does_not_infer_handoffs_from_execution_order() -> None:
    # Two different agents run the same mission, but NO explicit handoff event is emitted. The
    # registry must not invent one — explicit events are the source of truth (owner constraint).
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=QA, occurred_at=1.0))
    registry.observe(AgentCompleted(mission_id="m1", agent=QA, occurred_at=2.0))
    registry.observe(AgentStarted(mission_id="m1", agent=REVIEWER, occurred_at=3.0))
    mission = registry.mission_state("m1")
    assert mission is not None
    assert mission.handoffs == []  # not derived from ordering


def test_awaiting_approval_parks_the_active_agent_as_waiting() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=DEVELOPER, occurred_at=1.0))
    assert registry.state_for(DEVELOPER).status is AgentStatus.WORKING  # type: ignore[union-attr]
    registry.observe(
        MissionObserved(mission_id="m1", kind=MissionEventKind.AWAITING_APPROVAL, occurred_at=2.0)
    )
    assert registry.state_for(DEVELOPER).status is AgentStatus.WAITING  # type: ignore[union-attr]


def test_mission_completed_releases_participants_and_counts_once() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=QA, occurred_at=1.0))
    registry.observe(AgentCompleted(mission_id="m1", agent=QA, occurred_at=2.0))
    completed = MissionObserved(mission_id="m1", kind=MissionEventKind.COMPLETED, occurred_at=4.0)
    registry.observe(completed)
    registry.observe(completed)  # a duplicate terminal must not double-count
    state = registry.state_for(QA)
    assert state is not None
    assert state.status is AgentStatus.IDLE
    assert state.current_mission_id is None  # the binding is cleared on release
    assert state.completed_missions == 1


def test_blocked_agent_is_not_released_to_idle_on_completion() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=REVIEWER, occurred_at=1.0))
    registry.observe(
        AgentCompleted(mission_id="m1", agent=REVIEWER, verdict="block", occurred_at=2.0)
    )
    registry.observe(
        MissionObserved(mission_id="m1", kind=MissionEventKind.FAILED, occurred_at=3.0)
    )
    state = registry.state_for(REVIEWER)
    assert state is not None
    assert state.status is AgentStatus.BLOCKED  # a block survives a fail-safe terminal


def test_status_change_is_recorded_on_the_feed() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=QA, occurred_at=1.0))
    # The ingress event and the derived status-change both land on the recent-events feed.
    feed_kinds = [e.to_dict()["kind"] for e in registry.recent_events()]
    assert "AgentStarted" in feed_kinds
    assert "AgentStatusChanged" in feed_kinds


def test_unknown_agent_is_auto_registered_on_first_event() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=DEVELOPER, occurred_at=1.0))
    assert registry.state_for(DEVELOPER) is not None


# --- sessions --------------------------------------------------------------------------------


def test_started_opens_an_active_session_the_state_references() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0))
    state = registry.state_for(QA)
    assert state is not None
    assert state.active_session_id is not None
    active = registry.active_session_for(QA)
    assert active is not None
    assert active.is_active
    assert active.mission_id == "m1"
    assert active.step_id == "s1"
    assert active.started_at == 1.0
    assert registry.completed_sessions() == []  # nothing sealed yet


def test_completed_seals_the_session_into_immutable_history() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0))
    registry.observe(
        AgentCompleted(
            mission_id="m1",
            agent=QA,
            step_id="s1",
            duration_ms=42.0,
            output_summary="all suites green",
            occurred_at=2.0,
        )
    )
    assert registry.active_session_for(QA) is None  # released
    sessions = registry.completed_sessions()
    assert len(sessions) == 1
    sealed = sessions[0]
    assert sealed.status is SessionStatus.COMPLETED
    assert sealed.ended_at == 2.0
    assert sealed.duration_ms == 42.0
    assert sealed.output_summary == "all suites green"
    assert registry.sessions_for_mission("m1") == [sealed]


def test_decision_is_attached_to_the_active_session_then_sealed_with_it() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=REVIEWER, step_id="s1", occurred_at=1.0))
    registry.observe(
        AgentDecisionRecorded(
            mission_id="m1", agent=REVIEWER, verdict="approve", rationale="LGTM", occurred_at=2.0
        )
    )
    active = registry.active_session_for(REVIEWER)
    assert active is not None
    assert active.decision is not None
    assert active.decision.verdict == "approve"

    registry.observe(AgentCompleted(mission_id="m1", agent=REVIEWER, step_id="s1", occurred_at=3.0))
    sealed = registry.completed_sessions()[0]
    assert sealed.decision is not None
    assert sealed.decision.verdict == "approve"


def test_sessions_form_a_parent_child_tree_along_the_mission() -> None:
    # QA runs, then Reviewer runs — the Reviewer's session is a child of QA's (the relay chain).
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0))
    registry.observe(AgentCompleted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0))
    registry.observe(AgentStarted(mission_id="m1", agent=REVIEWER, step_id="s2", occurred_at=3.0))

    qa_session, reviewer_session = registry.sessions_for_mission("m1")
    assert qa_session.parent_session_id is None  # the first session has no parent
    assert reviewer_session.parent_session_id == qa_session.session_id
    # The parent's child link was completed after it sealed — append-only, execution facts intact.
    assert qa_session.child_session_ids == (reviewer_session.session_id,)
    assert qa_session.status is SessionStatus.COMPLETED


def test_completed_session_carries_artifacts_and_errors() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=DEVELOPER, step_id="s1", occurred_at=1.0))
    registry.observe(
        AgentCompleted(
            mission_id="m1",
            agent=DEVELOPER,
            step_id="s1",
            ok=False,
            artifacts=(ArtifactRef(kind="diff", title="fix.patch"),),
            errors=("boom",),
            occurred_at=2.0,
        )
    )
    sealed = registry.completed_sessions()[0]
    assert sealed.status is SessionStatus.FAILED  # ok=False -> FAILED session
    assert sealed.artifacts[0].kind == "diff"
    assert sealed.errors == ("boom",)


def test_completed_sessions_are_immutable_frozen_records() -> None:
    registry = AgentRuntimeRegistry()
    registry.observe(AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0))
    registry.observe(AgentCompleted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0))
    sealed = registry.completed_sessions()[0]
    with pytest.raises(FrozenInstanceError):
        sealed.output_summary = "tampered"  # type: ignore[misc]
