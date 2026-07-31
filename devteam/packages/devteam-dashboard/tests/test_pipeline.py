"""The /api/pipeline route: observed mission executions (the Mission Experience), read-only.

Reads the journal only through devteam_view_from_journal (a RuntimeStateView); the test writes a
real journal with JournalingObserver and asserts the shaped mission cards.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from devteam_dashboard import pipeline_view
from devteam_dashboard.app import create_app
from devteam_dashboard.config import DashboardConfig, load_config
from devteam_dashboard.runtime_gateway import RuntimeGateway
from devteam_observability import (
    AgentCompleted,
    AgentHandoffOccurred,
    AgentId,
    AgentStarted,
    AgentSubsystem,
    JournalingObserver,
    MissionEventKind,
    MissionObserved,
)
from fastapi.testclient import TestClient

_FIXTURES = Path(__file__).parent / "fixtures"
QA = AgentId(AgentSubsystem.PLATFORM, "qa")
REVIEWER = AgentId(AgentSubsystem.PLATFORM, "reviewer")


def _no_gateway() -> RuntimeGateway:
    raise AssertionError("the /api/pipeline route must not touch the runtime gateway")


def _write_relay(journal: Path) -> None:
    """A QA -> Reviewer mission with a handoff, sealed COMPLETED (two sessions, a parent/child)."""
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


def _write_in_flight(journal: Path) -> None:
    """A mission created with a QA session started but not yet sealed — one ACTIVE session, so the
    mission is non-terminal (the live stream stays open)."""
    writer = JournalingObserver(journal)
    for event in (
        MissionObserved(mission_id="m1", kind=MissionEventKind.CREATED, occurred_at=1.0),
        AgentStarted(mission_id="m1", agent=QA, step_id="s1", occurred_at=2.0),
    ):
        writer.observe(event)


def _collect(stream: AsyncIterator[str]) -> list[str]:
    """Drain an async SSE generator to a list (no pytest-asyncio needed)."""

    async def run() -> list[str]:
        return [frame async for frame in stream]

    return asyncio.run(run())


def _data_payloads(frames: list[str]) -> list[dict[str, object]]:
    return [json.loads(f[len("data: ") :].strip()) for f in frames if f.startswith("data: ")]


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


def test_pipeline_lists_observed_missions_with_a_session_summary(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    _write_relay(journal)

    body = _client(tmp_path, journal).get("/api/pipeline").json()
    assert body["journal_present"] is True
    assert len(body["missions"]) == 1
    mission = body["missions"][0]
    assert mission["mission_id"] == "m1"
    assert mission["owner"]["key"] == "platform:qa"  # first agent owns the mission
    assert mission["status"] == "completed"
    assert mission["session_count"] == 2 and mission["completed"] == 2
    assert [p["key"] for p in mission["participants"]] == ["platform:qa", "platform:reviewer"]


def test_pipeline_is_empty_without_a_journal(tmp_path: Path) -> None:
    body = _client(tmp_path, tmp_path / "absent.jsonl").get("/api/pipeline").json()
    assert body["journal_present"] is False
    assert body["missions"] == []


def test_mission_timeline_returns_ordered_sessions_with_the_tree(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    _write_relay(journal)

    body = _client(tmp_path, journal).get("/api/pipeline/m1").json()
    assert body["found"] is True
    assert body["mission_id"] == "m1" and body["status"] == "completed"
    sessions = body["sessions"]
    assert [s["step_id"] for s in sessions] == ["s1", "s2"]  # start order
    # The tree is the frozen view's, not rebuilt: the Reviewer session's parent is QA's session.
    assert sessions[0]["parent_session_id"] is None
    assert sessions[1]["parent_session_id"] == sessions[0]["session_id"]
    assert sessions[0]["child_session_ids"] == [sessions[1]["session_id"]]


def test_mission_timeline_reports_not_found_for_an_unknown_mission(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    _write_relay(journal)
    body = _client(tmp_path, journal).get("/api/pipeline/does-not-exist").json()
    assert body["found"] is False


# --- Live Pipeline (Increment 3): the SSE stream over the read_mission payload -----------------


def test_mission_signature_changes_when_a_session_seals(tmp_path: Path) -> None:
    in_flight = tmp_path / "in_flight.jsonl"
    sealed = tmp_path / "sealed.jsonl"
    _write_in_flight(in_flight)
    _write_relay(sealed)
    active = pipeline_view.read_mission(in_flight, "m1")
    done = pipeline_view.read_mission(sealed, "m1")
    # A moving mission and a finished one fingerprint differently; the same state fingerprints same.
    assert pipeline_view.mission_signature(active) != pipeline_view.mission_signature(done)
    assert pipeline_view.mission_signature(done) == pipeline_view.mission_signature(
        pipeline_view.read_mission(sealed, "m1")
    )
    assert pipeline_view.mission_is_terminal(done) is True
    assert pipeline_view.mission_is_terminal(active) is False


def test_mission_stream_emits_one_data_frame_then_done_for_a_terminal_mission(
    tmp_path: Path,
) -> None:
    journal = tmp_path / "runtime.jsonl"
    _write_relay(journal)
    frames = _collect(pipeline_view.mission_event_stream(journal, "m1", interval=0))
    payloads = _data_payloads(frames)
    assert len(payloads) == 1  # terminal on the first read → one frame, then done
    assert payloads[0]["mission_id"] == "m1" and payloads[0]["status"] == "completed"
    assert frames[-1].startswith("event: done")


def test_mission_stream_stays_open_and_deduplicates_for_an_in_flight_mission(
    tmp_path: Path,
) -> None:
    journal = tmp_path / "runtime.jsonl"
    _write_in_flight(journal)
    # Journal never changes across the bounded run → exactly one frame, and never a done event.
    frames = _collect(pipeline_view.mission_event_stream(journal, "m1", interval=0, max_ticks=4))
    payloads = _data_payloads(frames)
    assert len(payloads) == 1
    assert payloads[0]["status"] == "created" and payloads[0]["active"] == 1
    assert not any(f.startswith("event: done") for f in frames)


def test_mission_stream_ends_immediately_when_the_client_disconnects(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    _write_relay(journal)

    async def disconnected() -> bool:
        return True

    frames = _collect(
        pipeline_view.mission_event_stream(
            journal, "m1", is_disconnected=disconnected, interval=0
        )
    )
    assert frames == []


def test_mission_stream_endpoint_serves_an_event_stream(tmp_path: Path) -> None:
    journal = tmp_path / "runtime.jsonl"
    _write_relay(journal)
    client = _client(tmp_path, journal)
    lines: list[str] = []
    with client.stream("GET", "/api/pipeline/m1/stream") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            lines.append(line)
            if "event: done" in line or len(lines) > 40:
                break
    body = "\n".join(lines)
    assert '"mission_id": "m1"' in body
    assert "event: done" in body
