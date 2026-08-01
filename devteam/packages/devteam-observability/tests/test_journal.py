"""The journal transport: versioned records, deterministic replay, and the reader->view boundary."""

from __future__ import annotations

import json
from pathlib import Path

from devteam_observability import (
    JOURNAL_SCHEMA_VERSION,
    AgentCompleted,
    AgentDecisionRecorded,
    AgentHandoffOccurred,
    AgentId,
    AgentRuntimeRegistry,
    AgentStarted,
    AgentSubsystem,
    HandoffSource,
    JournalingObserver,
    JournalReader,
    MissionEventKind,
    MissionObserved,
    RuntimeEvent,
    RuntimeStateView,
    agent_id_for,
    devteam_view_from_journal,
)
from devteam_observability.adapter import ORG_ROSTER, PLATFORM_ROSTER
from devteam_protocol import AgentRole

QA = AgentId(AgentSubsystem.PLATFORM, "qa")
REVIEWER = AgentId(AgentSubsystem.PLATFORM, "reviewer")


def _relay_events() -> list[RuntimeEvent]:
    """A QA -> Reviewer relay exercising every ingress event type (and the session tree)."""
    return [
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0),
        AgentDecisionRecorded(mission_id="m1", agent=QA, verdict="proceed", occurred_at=1.5),
        AgentCompleted(
            mission_id="m1", agent=QA, step_id="s1", duration_ms=10.0, output_summary="ok",
            occurred_at=2.0,
        ),
        AgentHandoffOccurred(
            mission_id="m1", from_agent=QA, to_agent=REVIEWER, source=HandoffSource.OBSERVED,
            occurred_at=2.2,
        ),
        AgentStarted(mission_id="m1", agent=REVIEWER, step_id="s2", occurred_at=3.0),
        AgentCompleted(mission_id="m1", agent=REVIEWER, step_id="s2", occurred_at=4.0),
        MissionObserved(mission_id="m1", kind=MissionEventKind.COMPLETED, occurred_at=5.0),
    ]


def test_replay_reproduces_state_exactly(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    live = AgentRuntimeRegistry()
    for event in _relay_events():
        live.observe(event)
        writer.observe(event)

    replayed = JournalReader(journal).replay()

    # Deterministic: same facts, same order -> identical sessions (ids, tree, decision) and mission.
    assert [s.to_dict() for s in replayed.completed_sessions()] == [
        s.to_dict() for s in live.completed_sessions()
    ]
    live_mission = live.mission_state("m1")
    replayed_mission = replayed.mission_state("m1")
    assert live_mission is not None and replayed_mission is not None
    assert replayed_mission.to_dict() == live_mission.to_dict()


def test_every_record_is_versioned(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    JournalingObserver(journal).observe(
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0)
    )
    record = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])
    assert record["schema_version"] == JOURNAL_SCHEMA_VERSION
    assert record["event"]["kind"] == "AgentStarted"


def test_a_record_from_an_unknown_schema_version_is_skipped(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    valid = AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0)
    lines = [
        json.dumps({"schema_version": 999, "event": {"kind": "AgentStarted", "mission_id": "mX"}}),
        json.dumps({"schema_version": JOURNAL_SCHEMA_VERSION, "event": valid.to_dict()}),
    ]
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")

    registry = JournalReader(journal).replay()
    # Only the v1 record folded — the future-version one was skipped, not misread.
    assert registry.state_for(QA) is not None
    assert registry.mission_state("mX") is None


def test_missing_journal_yields_an_empty_view(tmp_path: Path) -> None:
    view = JournalReader(tmp_path / "absent.jsonl").view()
    assert view.agents() == []


def test_dashboard_reads_a_seeded_view_never_the_file(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    for event in _relay_events():
        writer.observe(event)

    # The Dashboard-side entry point returns a RuntimeStateView (the storage stays hidden).
    view = devteam_view_from_journal(journal)
    assert isinstance(view, RuntimeStateView)
    # The whole platform roster (engineering squad + AI Organization) is seeded on the reader side.
    assert len(view.agents()) == len(PLATFORM_ROSTER) + len(ORG_ROSTER)
    qa = view.agent(agent_id_for(AgentRole.QA))
    assert qa is not None
    assert qa["executions"] == 1
    assert view.ownership() == {"m1": "platform:qa"}
