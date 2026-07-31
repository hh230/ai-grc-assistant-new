"""The JobScheduler — one scheduler inside the existing organization service (§11).

It wakes on every organization tick, asks each job whether it is due, and executes ONLY the due ones
(a cheap ``is_due`` check — no busy waiting, no thread per job). For each executed job it: records
JobStarted, runs the inspection, times it, folds the outcome into the job's ``JobState``,
opens a REAL Mission via the runtime **iff** the job returned a ``MissionRequest`` (evidence),
records JobCompleted / MissionCreated / JobErrored, and rewrites the snapshot the Dashboard reads.

It is NOT a second runtime: mission creation is delegated to the injected ``open_mission`` (wired to
the existing ``OrganizationRuntime``), so every job-created mission flows through the one frozen
Mission Engine and lands in the shared runtime journal like any other mission.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from mission_engine.mission import Mission

from devteam_organization.jobs.framework import (
    ExecutionResult,
    Job,
    JobContext,
    JobHealth,
    JobResult,
    JobState,
    MissionRequest,
)
from devteam_organization.jobs.journal import (
    JobEvent,
    JobEventKind,
    JobJournalSink,
    NullJobJournal,
)

_LOG = logging.getLogger("devteam.organization.jobs")

# Open a real Mission from a job's evidence. Injected so the scheduler stays decoupled from the
# runtime and testable; the composition wires it to ``OrganizationRuntime.run_mission``.
OpenMission = Callable[[MissionRequest], Mission | None]

# The live read view for jobs that inspect the runtime (runtime health, CEO KPIs). Injected.
ViewProvider = Callable[[], object]


@dataclass(frozen=True)
class JobRun:
    """The outcome of one executed job this tick — for observability and tests."""

    job_id: str
    result: JobResult | None
    mission: Mission | None
    error: str | None = None

    @property
    def created_mission(self) -> bool:
        return self.mission is not None


class JobScheduler:
    """Holds the jobs + their state; ``tick`` runs the due ones. Construct once at startup."""

    def __init__(
        self,
        jobs: Iterable[Job],
        *,
        open_mission: OpenMission,
        repo_root: Path | str,
        journal: JobJournalSink | None = None,
        view_provider: ViewProvider | None = None,
        clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._jobs: list[Job] = list(jobs)
        self._states: dict[str, JobState] = {job.id: JobState.from_job(job) for job in self._jobs}
        self._open = open_mission
        self._repo_root = Path(repo_root)
        self._journal = journal or NullJobJournal()
        self._view_provider = view_provider
        self._clock = clock
        self._monotonic = monotonic
        # Publish the seeded roster so the Dashboard shows every job before it first runs.
        self._journal.write_snapshot(self.states())

    def states(self) -> list[JobState]:
        return [self._states[job.id] for job in self._jobs]

    def state(self, job_id: str) -> JobState | None:
        return self._states.get(job_id)

    def tick(self) -> list[JobRun]:
        """One scheduler pass: execute every enabled, due job once. Returns the runs (for tests /
        the caller); a job's own failure is contained — it never aborts the pass."""
        now = self._clock()
        view = self._view_provider() if self._view_provider is not None else None
        context = JobContext(now=now, repo_root=self._repo_root, view=view)  # type: ignore[arg-type]
        runs: list[JobRun] = []
        for job in self._jobs:
            state = self._states[job.id]
            if not state.enabled:
                continue
            if not job.schedule.is_due(now=now, next_run=state.next_run):
                continue
            runs.append(self._run(job, state, context))
        self._journal.write_snapshot(self.states())
        return runs

    def _run(self, job: Job, state: JobState, context: JobContext) -> JobRun:
        self._journal.record(
            JobEvent(
                kind=JobEventKind.JOB_STARTED,
                occurred_at=self._clock(),
                job_id=job.id,
                name=job.name,
                owner=job.owner.value,
            )
        )
        started = self._monotonic()
        try:
            result = job.inspect(context)
        except Exception as exc:  # a job must never crash the scheduler
            duration = max(0.0, (self._monotonic() - started) * 1000.0)
            _LOG.exception("job %s failed", job.id)
            self._fold_error(job, state, context.now, duration, repr(exc))
            return JobRun(job_id=job.id, result=None, mission=None, error=repr(exc))

        duration = max(0.0, (self._monotonic() - started) * 1000.0)
        mission = self._fold_result(job, state, context.now, duration, result)
        return JobRun(job_id=job.id, result=result, mission=mission)

    def _fold_result(
        self, job: Job, state: JobState, now: float, duration_ms: float, result: JobResult
    ) -> Mission | None:
        state.last_run = now
        state.last_duration_ms = duration_ms
        state.next_run = job.schedule.next_after(now)
        state.last_summary = result.summary

        mission: Mission | None = None
        if result.mission_request is not None:
            # Real evidence → a real Mission through the runtime. This is the ONLY path that acts.
            mission = self._open(result.mission_request)
            if mission is not None:
                state.created_missions += 1
                state.last_mission_id = mission.id
                kind = (
                    JobEventKind.MISSION_ESCALATED
                    if result.mission_request.escalate
                    else JobEventKind.MISSION_CREATED
                )
                self._journal.record(
                    JobEvent(
                        kind=kind,
                        occurred_at=self._clock(),
                        job_id=job.id,
                        name=job.name,
                        owner=job.owner.value,
                        summary=result.mission_request.goal,
                        mission_id=mission.id,
                    )
                )
            state.health = JobHealth.DEGRADED
            state.execution_result = ExecutionResult.ACTION_TAKEN
        else:
            # Nothing found → record a successful, idle execution. No fabrication.
            state.health = result.health
            state.execution_result = ExecutionResult.OK

        self._journal.record(
            JobEvent(
                kind=JobEventKind.JOB_COMPLETED,
                occurred_at=self._clock(),
                job_id=job.id,
                name=job.name,
                owner=job.owner.value,
                summary=result.summary,
                health=state.health.value,
                duration_ms=duration_ms,
                mission_id=mission.id if mission is not None else None,
            )
        )
        return mission

    def _fold_error(
        self, job: Job, state: JobState, now: float, duration_ms: float, error: str
    ) -> None:
        state.last_run = now
        state.last_duration_ms = duration_ms
        state.next_run = job.schedule.next_after(now)
        state.health = JobHealth.UNHEALTHY
        state.execution_result = ExecutionResult.ERROR
        state.last_summary = f"error: {error}"
        self._journal.record(
            JobEvent(
                kind=JobEventKind.JOB_ERRORED,
                occurred_at=self._clock(),
                job_id=job.id,
                name=job.name,
                owner=job.owner.value,
                summary=error,
                health=JobHealth.UNHEALTHY.value,
                duration_ms=duration_ms,
            )
        )


def open_mission_via_runtime(run_mission: Callable[..., Mission]) -> OpenMission:
    """Wire the scheduler's mission opener to ``OrganizationRuntime.run_mission`` — a job's evidence
    becomes a real, governed org mission (CEO→…→DevTeam, scoped by the request's stages)."""

    def opener(request: MissionRequest) -> Mission | None:
        stages = list(request.stages) if request.stages else None
        return run_mission(request.goal, stages=stages)

    return opener
