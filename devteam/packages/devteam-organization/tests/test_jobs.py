"""The Jobs framework — schedule, gate, scheduler, journal."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devteam_organization import OrganizationRuntime
from devteam_organization.jobs import (
    ExecutionResult,
    FileJobJournal,
    JobEvent,
    JobEventKind,
    JobHealth,
    JobResult,
    JobScheduler,
    JobState,
    MissionGate,
    MissionRequest,
    Observation,
    Schedule,
    open_mission_via_runtime,
    read_jobs_snapshot,
)
from devteam_protocol import AgentCapability, AgentRole


class _StubJob:
    connector_id = ""

    def __init__(
        self,
        job_id: str,
        outcome: JobResult | Exception,
        *,
        schedule: Schedule,
        owner: AgentRole = AgentRole.CISO,
    ) -> None:
        self.id = job_id
        self.name = job_id
        self.owner = owner
        self.schedule = schedule
        self._outcome = outcome

    def inspect(self, context: object) -> JobResult:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class _RecordingJournal:
    def __init__(self) -> None:
        self.events: list[JobEvent] = []
        self.snapshots: list[list[str]] = []

    def record(self, event: JobEvent) -> None:
        self.events.append(event)

    def write_snapshot(self, states: Sequence[JobState]) -> None:
        self.snapshots.append([s.id for s in states])


def test_schedule_is_due() -> None:
    interval = Schedule(600.0)
    assert interval.is_due(now=100.0, next_run=None)
    assert not interval.is_due(now=100.0, next_run=200.0)
    assert interval.is_due(now=250.0, next_run=200.0)
    assert Schedule(0.0, every_tick=True).is_due(now=1.0, next_run=1e9)


def test_mission_gate_edge_triggers_one_mission_per_episode() -> None:
    gate = MissionGate()
    first = gate.evaluate(signature="x", goal="g", degraded_summary="d", healthy_summary="h")
    assert first.mission_request is not None
    ongoing = gate.evaluate(signature="x", goal="g", degraded_summary="d", healthy_summary="h")
    assert ongoing.mission_request is None and ongoing.health is JobHealth.DEGRADED
    cleared = gate.evaluate(signature="", goal="g", degraded_summary="d", healthy_summary="h")
    assert cleared.health is JobHealth.HEALTHY
    rearmed = gate.evaluate(signature="x", goal="g", degraded_summary="d", healthy_summary="h")
    assert rearmed.mission_request is not None


def test_scheduler_runs_due_jobs_and_opens_missions_only_on_evidence(
    runtime: OrganizationRuntime,
) -> None:
    journal = _RecordingJournal()
    evidence = JobResult(
        JobHealth.DEGRADED,
        "problem",
        (Observation("bad", "high"),),
        MissionRequest("CISO: fix a security issue", (AgentCapability.SECURITY_REVIEW,)),
    )
    scheduler = JobScheduler(
        [
            _StubJob("j.evidence", evidence, schedule=Schedule(600.0)),
            _StubJob("j.healthy", JobResult.healthy("all good"), schedule=Schedule(600.0)),
        ],
        open_mission=open_mission_via_runtime(runtime.run_mission),
        repo_root=".",
        journal=journal,
        clock=lambda: 1000.0,
    )
    runs = scheduler.tick()
    assert len(runs) == 2

    evid = scheduler.state("j.evidence")
    assert evid is not None
    assert evid.execution_result is ExecutionResult.ACTION_TAKEN
    assert evid.created_missions == 1 and evid.last_mission_id is not None

    good = scheduler.state("j.healthy")
    assert good is not None and good.execution_result is ExecutionResult.OK
    assert good.created_missions == 0 and good.health is JobHealth.HEALTHY

    kinds = {event.kind for event in journal.events}
    expected = {JobEventKind.JOB_STARTED, JobEventKind.JOB_COMPLETED, JobEventKind.MISSION_CREATED}
    assert expected <= kinds
    assert journal.snapshots


def test_scheduler_skips_jobs_that_are_not_due() -> None:
    job = _StubJob("j", JobResult.healthy("ok"), schedule=Schedule(600.0))
    scheduler = JobScheduler(
        [job], open_mission=lambda _r: None, repo_root=".", clock=lambda: 1000.0
    )
    assert len(scheduler.tick()) == 1
    assert scheduler.tick() == []


def test_scheduler_contains_a_job_error() -> None:
    journal = _RecordingJournal()
    job = _StubJob("j.bad", RuntimeError("boom"), schedule=Schedule(600.0))
    scheduler = JobScheduler(
        [job], open_mission=lambda _r: None, repo_root=".", journal=journal, clock=lambda: 1.0
    )
    runs = scheduler.tick()
    assert runs[0].error is not None
    state = scheduler.state("j.bad")
    assert state is not None and state.health is JobHealth.UNHEALTHY
    assert JobEventKind.JOB_ERRORED in {event.kind for event in journal.events}


def test_file_journal_writes_events_and_a_readable_snapshot(tmp_path: Path) -> None:
    events = tmp_path / "jobs.jsonl"
    snapshot = tmp_path / "jobs.json"
    journal = FileJobJournal(events, snapshot)
    journal.record(
        JobEvent(JobEventKind.JOB_COMPLETED, 1.0, "ciso.tls", "TLS", "ciso", health="healthy")
    )
    state = JobState(id="ciso.tls", name="TLS", owner=AgentRole.CISO, schedule_seconds=600.0)
    journal.write_snapshot([state])

    assert events.read_text().strip()
    payload = read_jobs_snapshot(snapshot)
    assert payload["snapshot_present"] is True
    jobs = payload["jobs"]
    assert isinstance(jobs, list) and jobs[0]["id"] == "ciso.tls"


def test_read_snapshot_absent_is_empty_not_error(tmp_path: Path) -> None:
    payload = read_jobs_snapshot(tmp_path / "missing.json")
    assert payload == {"jobs": [], "snapshot_present": False}
