"""The /api/agents route: the live roster rebuilt from the runtime journal (read-only, resilient).

The route reads the journal only through devteam_view_from_journal (a RuntimeStateView), never the
file — so these tests write a real journal with JournalingObserver and assert the shaped response.
"""

from __future__ import annotations

from pathlib import Path

from devteam_dashboard.app import create_app
from devteam_dashboard.config import DashboardConfig, load_config
from devteam_dashboard.runtime_gateway import RuntimeGateway
from devteam_observability import (
    AgentCompleted,
    AgentDecisionRecorded,
    AgentHandoffOccurred,
    AgentId,
    AgentStarted,
    AgentSubsystem,
    JournalingObserver,
    MissionEventKind,
    MissionObserved,
)
from devteam_observability.adapter import ORG_ROSTER, PLATFORM_ROSTER
from fastapi.testclient import TestClient

_FIXTURES = Path(__file__).parent / "fixtures"
QA = AgentId(AgentSubsystem.PLATFORM, "qa")
REVIEWER = AgentId(AgentSubsystem.PLATFORM, "reviewer")


def _no_gateway() -> RuntimeGateway:
    raise AssertionError("the /api/agents route must not touch the runtime gateway")


def _client(tmp_path: Path, journal: Path) -> TestClient:
    config: DashboardConfig = load_config(
        plist_path=_FIXTURES / "com.rasheed.devteam-monitor.plist",
        repo="o/r",
        repo_root=tmp_path,
        log_path=_FIXTURES / "monitor.err.log",
        actions_log_path=tmp_path / "actions.jsonl",
        journal_path=journal,
    )
    return TestClient(create_app(config, gateway_factory=_no_gateway))


def test_agents_shows_the_seeded_idle_roster_when_no_journal(tmp_path: Path) -> None:
    body = _client(tmp_path, tmp_path / "absent.jsonl").get("/api/agents").json()
    assert body["journal_present"] is False
    # The whole platform (engineering squad + AI Organization) is visible before any activity.
    assert len(body["agents"]) == len(PLATFORM_ROSTER) + len(ORG_ROSTER)
    assert all(a["status"] == "idle" for a in body["agents"])
    assert body["sessions"] == []
    # The AI Organization renders automatically — no dashboard change, just the roster it seeds.
    keys = {a["agent"]["key"] for a in body["agents"]}
    assert {
        "platform:ceo",
        "platform:cto",
        "platform:ciso",
        "platform:grc_expert",
        "platform:devteam",
        "platform:supervisor",
    } <= keys


def test_agents_reflects_journalled_activity(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    for event in (
        MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0),
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0),
        AgentCompleted(mission_id="m1", agent=QA, step_id="s1", duration_ms=12.0, occurred_at=3.0),
        MissionObserved(mission_id="m1", kind=MissionEventKind.COMPLETED, occurred_at=4.0),
    ):
        writer.observe(event)

    body = _client(tmp_path, journal).get("/api/agents").json()
    assert body["journal_present"] is True
    assert body["ownership"] == {"m1": "platform:qa"}
    qa = next(a for a in body["agents"] if a["agent"]["key"] == "platform:qa")
    assert qa["executions"] == 1 and qa["status"] == "idle"
    assert len(body["sessions"]) == 1 and body["sessions"][0]["status"] == "completed"


def test_agents_survives_a_torn_journal_line(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    JournalingObserver(journal).observe(
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=1.0)
    )
    # Simulate the daemon mid-append: a partial JSON line with no newline at the end of the file.
    with journal.open("a", encoding="utf-8") as handle:
        handle.write('{"schema_version": 1, "event": {"kind": "AgentComple')

    body = _client(tmp_path, journal).get("/api/agents").json()
    # The complete line folded; the torn one was skipped — no crash, agent shows as working.
    qa = next(a for a in body["agents"] if a["agent"]["key"] == "platform:qa")
    assert qa["status"] == "working"


# --- Agent Inspector (Agent Experience): the /api/agents/{key} drill-down ----------------------


def test_agent_detail_returns_one_agents_state_and_its_own_sessions(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    for event in (
        MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0),
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0),
        AgentCompleted(mission_id="m1", agent=QA, step_id="s1", duration_ms=12.0, occurred_at=3.0),
        MissionObserved(mission_id="m1", kind=MissionEventKind.COMPLETED, occurred_at=4.0),
    ):
        writer.observe(event)

    body = _client(tmp_path, journal).get("/api/agents/platform:qa").json()
    assert body["found"] is True
    assert body["agent"]["key"] == "platform:qa"
    assert body["executions"] == 1 and body["status"] == "idle"
    # The inspector carries only THIS agent's sessions (the QA step), oldest-first.
    assert [s["step_id"] for s in body["sessions"]] == ["s1"]
    assert all(s["agent"]["key"] == "platform:qa" for s in body["sessions"])


def test_agent_detail_includes_the_in_flight_session(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    for event in (
        MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0),
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0),
    ):
        writer.observe(event)

    body = _client(tmp_path, journal).get("/api/agents/platform:qa").json()
    assert body["found"] is True and body["status"] == "working"
    assert [s["status"] for s in body["sessions"]] == ["active"]  # the live step is shown
    assert body["current_mission_id"] == "m1"


def test_agent_detail_reports_not_found_for_an_unknown_key(tmp_path: Path) -> None:
    body = _client(tmp_path, tmp_path / "absent.jsonl").get("/api/agents/platform:ghost").json()
    assert body["found"] is False
    assert body["agent_key"] == "platform:ghost"


def test_seeded_roster_agent_is_inspectable_before_any_activity(tmp_path: Path) -> None:
    # No journal: the seeded idle roster is still inspectable (found), with an empty timeline.
    body = _client(tmp_path, tmp_path / "absent.jsonl").get("/api/agents/platform:reviewer").json()
    assert body["found"] is True and body["status"] == "idle"
    assert body["sessions"] == []


def test_agent_timeline_tags_a_handoff_predecessor(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    for event in (
        MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0),
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0),
        AgentCompleted(mission_id="m1", agent=QA, step_id="s1", occurred_at=3.0),
        AgentHandoffOccurred(mission_id="m1", from_agent=QA, to_agent=REVIEWER, occurred_at=3.5),
        AgentStarted(mission_id="m1", agent=REVIEWER, step_id="s2", occurred_at=4.0),
        AgentCompleted(mission_id="m1", agent=REVIEWER, step_id="s2", occurred_at=5.0),
        MissionObserved(mission_id="m1", kind=MissionEventKind.COMPLETED, occurred_at=6.0),
    ):
        writer.observe(event)

    client = _client(tmp_path, journal)
    reviewer = client.get("/api/agents/platform:reviewer").json()
    # The Reviewer's session followed QA's on the same mission -> tagged with the predecessor agent.
    assert reviewer["sessions"][0]["handoff_from"]["key"] == "platform:qa"
    # QA started the mission -> no predecessor, so no handoff tag.
    qa = client.get("/api/agents/platform:qa").json()
    assert "handoff_from" not in qa["sessions"][0]


# --- Agent Operational Metrics (Increment 3) --------------------------------------------------


def _run_session(
    writer: JournalingObserver, mission: str, index: int, duration_ms: float, verdict: str
) -> None:
    base = index * 10.0
    step = f"s{index}"
    writer.observe(
        MissionObserved(mission_id=mission, kind=MissionEventKind.CREATED, occurred_at=base)
    )
    writer.observe(AgentStarted(mission_id=mission, agent=QA, step_id=step, occurred_at=base + 1))
    writer.observe(
        AgentDecisionRecorded(
            mission_id=mission, agent=QA, verdict=verdict, rationale="", occurred_at=base + 1.5
        )
    )
    writer.observe(
        AgentCompleted(
            mission_id=mission, agent=QA, step_id=step,
            duration_ms=duration_ms, verdict=verdict, occurred_at=base + 2,
        )
    )
    writer.observe(
        MissionObserved(mission_id=mission, kind=MissionEventKind.COMPLETED, occurred_at=base + 3)
    )


def test_agent_metrics_are_measured_not_estimated(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    _run_session(writer, "m1", 1, 100.0, "proceed")
    _run_session(writer, "m2", 2, 200.0, "proceed")
    _run_session(writer, "m3", 3, 300.0, "request_changes")

    m = _client(tmp_path, journal).get("/api/agents/platform:qa").json()["metrics"]
    assert m["session_count"] == 3
    assert m["active_ms"] == 600.0
    assert m["avg_duration_ms"] == 200.0
    assert m["median_duration_ms"] == 200.0  # 3 timed sessions -> a real median
    assert m["decision_distribution"] == {"proceed": 2, "request_changes": 1}
    assert m["missions_worked"] == 3 and m["missions_completed"] == 3
    assert m["utilized"] is False and m["status"] == "idle"
    # Most-recent mission first, cross-linkable into Mission Experience.
    assert [e["mission_id"] for e in m["recent_missions"]] == ["m3", "m2", "m1"]
    assert m["idle_ms"] is not None  # a measurable span exists


def test_agent_median_needs_enough_data_and_is_not_fabricated(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    _run_session(writer, "m1", 1, 120.0, "proceed")

    m = _client(tmp_path, journal).get("/api/agents/platform:qa").json()["metrics"]
    assert m["session_count"] == 1 and m["avg_duration_ms"] == 120.0
    assert m["median_duration_ms"] is None  # below the threshold -> not invented
    assert m["median_min_sessions"] == 3


def test_agent_metrics_present_but_empty_for_an_idle_seeded_agent(tmp_path: Path) -> None:
    body = _client(tmp_path, tmp_path / "x.jsonl").get("/api/agents/platform:foreman").json()
    m = body["metrics"]
    assert m["session_count"] == 0 and m["active_ms"] == 0
    assert m["idle_ms"] is None and m["avg_duration_ms"] is None and m["median_duration_ms"] is None
    assert m["decision_distribution"] == {} and m["recent_missions"] == []
    assert m["queue"]["participating"] is False


def test_agent_metrics_report_live_queue_participation(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    writer.observe(MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0))
    writer.observe(AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0))

    m = _client(tmp_path, journal).get("/api/agents/platform:qa").json()["metrics"]
    assert m["utilized"] is True and m["status"] == "working"
    assert m["queue"]["participating"] is True and m["queue"]["mission_id"] == "m1"
