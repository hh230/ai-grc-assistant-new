"""The /api/executive route: the command-center overview, aggregated from the Mission + Agent
Experiences. Reads the journal only through devteam_view_from_journal (a RuntimeStateView); the
tests write a real journal and assert the roll-up counts (aggregation, not recomputed differently).
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
# The whole seeded platform roster: the engineering squad plus the AI Organization.
_ROSTER = len(PLATFORM_ROSTER) + len(ORG_ROSTER)


def _no_gateway() -> RuntimeGateway:
    raise AssertionError("the /api/executive route must not touch the runtime gateway")


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


def _decision(mid: str, agent: AgentId, verdict: str, at: float) -> AgentDecisionRecorded:
    return AgentDecisionRecorded(mission_id=mid, agent=agent, verdict=verdict, occurred_at=at)


def _completed(mid: str, agent: AgentId, dur: float, verdict: str, at: float) -> AgentCompleted:
    return AgentCompleted(
        mission_id=mid, agent=agent, duration_ms=dur, verdict=verdict, occurred_at=at
    )


def _seed_fleet(journal: Path) -> None:
    """Two completed missions (a QA->Reviewer relay, and a QA request_changes) plus one in flight
    with QA working — enough to exercise every roll-up."""
    writer = JournalingObserver(journal)
    for event in (
        MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0),
        AgentStarted(mission_id="m1", agent=QA, step_id="run", occurred_at=2.0),
        _decision("m1", QA, "proceed", 2.5),
        _completed("m1", QA, 100.0, "proceed", 3.0),
        AgentHandoffOccurred(mission_id="m1", from_agent=QA, to_agent=REVIEWER, occurred_at=3.5),
        AgentStarted(mission_id="m1", agent=REVIEWER, step_id="review", occurred_at=4.0),
        _decision("m1", REVIEWER, "approve", 4.5),
        _completed("m1", REVIEWER, 200.0, "approve", 5.0),
        MissionObserved(mission_id="m1", kind=MissionEventKind.COMPLETED, occurred_at=6.0),
        MissionObserved(mission_id="m2", kind=MissionEventKind.CREATED, occurred_at=10.0),
        AgentStarted(mission_id="m2", agent=QA, step_id="run", occurred_at=11.0),
        _decision("m2", QA, "request_changes", 11.5),
        _completed("m2", QA, 150.0, "request_changes", 12.0),
        MissionObserved(mission_id="m2", kind=MissionEventKind.COMPLETED, occurred_at=13.0),
        MissionObserved(mission_id="m3", kind=MissionEventKind.CREATED, occurred_at=20.0),
        AgentStarted(mission_id="m3", agent=QA, step_id="assess", occurred_at=21.0),
    ):
        writer.observe(event)


def test_executive_overview_aggregates_missions_and_agents(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    _seed_fleet(journal)

    body = _client(tmp_path, journal).get("/api/executive").json()
    assert body["journal_present"] is True

    missions = body["missions"]
    assert missions["total"] == 3 and missions["active"] == 1 and missions["completed"] == 2
    assert [m["mission_id"] for m in missions["active_list"]] == ["m3"]
    assert missions["active_list"][0]["owner"] == "platform:qa"

    agents = body["agents"]
    assert agents["total"] == _ROSTER and agents["utilized"] == 1  # QA is working on m3
    assert agents["engaged"] == 1

    assert body["throughput"]["completed_missions"] == 2
    # Fleet decision distribution is the additive sum across agents (QA + Reviewer).
    assert body["decision_distribution"] == {"proceed": 1, "approve": 1, "request_changes": 1}
    assert body["queue"]["health"] == "healthy"
    assert body["utilization"]["utilized_now"] == 1
    assert body["utilization"]["total_agents"] == _ROSTER
    assert abs(body["utilization"]["ratio_now"] - 1 / _ROSTER) < 1e-9


def test_executive_overview_is_empty_and_honest_without_a_journal(tmp_path: Path) -> None:
    body = _client(tmp_path, tmp_path / "absent.jsonl").get("/api/executive").json()
    assert body["journal_present"] is False
    assert body["missions"]["total"] == 0 and body["missions"]["active_list"] == []
    assert body["agents"]["total"] == _ROSTER and body["agents"]["utilized"] == 0  # idle roster
    assert body["decision_distribution"] == {}
    assert body["queue"]["health"] == "idle"
    # No sessions -> no measurable window -> "insufficient data", never a fabricated ratio.
    assert body["utilization"]["ratio_window"] is None
    assert body["utilization"]["ratio_now"] == 0.0


def test_executive_queue_health_flags_awaiting_approval(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    for event in (
        MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0),
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0),
        MissionObserved(mission_id="m1", kind=MissionEventKind.AWAITING_APPROVAL, occurred_at=3.0),
    ):
        writer.observe(event)

    body = _client(tmp_path, journal).get("/api/executive").json()
    assert body["missions"]["awaiting_approval"] == 1
    assert body["queue"]["awaiting_approval"] == 1 and body["queue"]["health"] == "attention"


# --- Increment 2: the Organization View roll-up ------------------------------------------------


def test_organization_view_rolls_up_fleet_and_agent_performance(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    _seed_fleet(journal)

    org = _client(tmp_path, journal).get("/api/executive").json()["organization"]

    # Fleet status distribution counts every roster member once (QA working on m3, the rest idle).
    dist = org["fleet"]["status_distribution"]
    assert sum(dist.values()) == _ROSTER and dist.get("working") == 1
    assert org["fleet"]["utilization"]["utilized_now"] == 1

    # The agent-performance table reuses agent_metrics (completed, avg, decisions, assignment).
    rows = {r["agent"]["key"]: r for r in org["agent_performance"]}
    assert len(rows) == _ROSTER
    qa = rows["platform:qa"]
    assert qa["completed_missions"] == 2 and qa["current_mission_id"] == "m3"
    assert qa["decision_distribution"] == {"proceed": 1, "request_changes": 1}
    assert qa["avg_duration_ms"] == 125.0  # (100 + 150) / 2 — same avg the Agent Inspector shows


def test_organization_mission_and_operational_sections(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    _seed_fleet(journal)

    org = _client(tmp_path, journal).get("/api/executive").json()["organization"]

    mp = org["mission_performance"]
    assert mp["lifecycle_distribution"].get("completed") == 2
    assert mp["completed_missions"] == 2
    assert mp["avg_completion_ms"] is not None  # measured from the two completed missions' spans

    oh = org["operational_health"]
    assert [m["mission_id"] for m in oh["long_running"]] == ["m3"]  # the one in-flight mission
    assert oh["long_running"][0]["active_since"] == 21.0  # its active session's start (not guessed)
    assert oh["idle_capacity"]["total"] == _ROSTER


def test_organization_avg_completion_is_insufficient_data_without_completed_missions(
    tmp_path: Path,
) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    # A single in-flight mission — nothing completed, so there is no completion time to report.
    writer.observe(MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0))
    writer.observe(AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0))

    org = _client(tmp_path, journal).get("/api/executive").json()["organization"]
    assert org["mission_performance"]["avg_completion_ms"] is None  # not fabricated


# --- Increment 3: the Operations Intelligence (insights) layer ---------------------------------


def test_insights_compose_attention_capacity_and_summary(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    _seed_fleet(journal)  # 2 completed + 1 in flight; QA working on m3, the rest idle

    ins = _client(tmp_path, journal).get("/api/executive").json()["insights"]

    ar = ins["attention_required"]
    # In flight m3 is long-running; QA is the queue hotspot (engaged); nothing blocked/awaiting.
    assert [m["mission_id"] for m in ar["long_running"]] == ["m3"]
    assert ar["waiting_approvals"] == [] and ar["stalled"] == []
    assert [a["agent"]["key"] for a in ar["queue_hotspots"]] == ["platform:qa"]

    co = ins["capacity_outlook"]
    assert co["utilized"] == 1 and co["total"] == _ROSTER
    # Every idle agent drill-links (the whole roster minus the one working).
    assert co["idle"] == _ROSTER - 1 and len(co["available_agents"]) == _ROSTER - 1

    # The summary is plain observed facts — utilization first, then the non-zero counts.
    summary = ins["operational_summary"]
    assert summary[0].startswith("Fleet utilization is")
    assert "1 mission in flight." in summary
    assert "1 agent currently working." in summary
    assert f"{_ROSTER - 1} agents currently idle." in summary
    assert "2 missions completed." in summary


def test_insights_summary_on_an_idle_seeded_roster(tmp_path: Path) -> None:
    ins = _client(tmp_path, tmp_path / "absent.jsonl").get("/api/executive").json()["insights"]
    # 0 of the whole roster utilized is a real, observed fact — reported as 0%, not hidden.
    assert ins["operational_summary"][0] == "Fleet utilization is 0%."
    assert f"{_ROSTER} agents currently idle." in ins["operational_summary"]
    assert ins["capacity_outlook"]["idle"] == _ROSTER
    assert ins["attention_required"]["queue_hotspots"] == []


def test_insights_flag_awaiting_approval_as_attention_and_hotspot(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    writer = JournalingObserver(journal)
    for event in (
        MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0),
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0),
        MissionObserved(mission_id="m1", kind=MissionEventKind.AWAITING_APPROVAL, occurred_at=3.0),
    ):
        writer.observe(event)

    ar = _client(tmp_path, journal).get("/api/executive").json()["insights"]["attention_required"]
    assert [m["mission_id"] for m in ar["waiting_approvals"]] == ["m1"]
    # QA is parked WAITING at the gate -> it surfaces as a queue hotspot (drill-links to the agent).
    assert [a["agent"]["key"] for a in ar["queue_hotspots"]] == ["platform:qa"]
