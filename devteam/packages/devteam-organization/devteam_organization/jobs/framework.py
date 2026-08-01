"""The AI Organization Jobs framework — recurring departmental responsibilities (§11).

An agent no longer only waits for a manually submitted mission: it OWNS recurring jobs that run on a
schedule, inspect a REAL source, and open a Mission *only when evidence requires it*. This
is the generic contract; the jobs and the scheduler are realizations of it.

The load-bearing rule (owner constraint): **a job never fabricates activity.** When everything it
inspects is healthy, it records a successful, idle execution — no Mission. A ``MissionRequest`` is
returned ONLY when the inspection found real evidence. The framework cannot force honesty, but it
gives every job one place to express it (``JobResult.mission_request``), and the jobs honor it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from devteam_protocol import AgentCapability, AgentRole

if TYPE_CHECKING:  # the view is a read-only façade; import only for typing to avoid a hard dep here
    from devteam_observability import RuntimeStateView


class JobHealth(str, Enum):
    """The health a job reports after an inspection — a projection of what it observed, not a guess.

    UNKNOWN   — never run yet (seeded state).
    HEALTHY   — ran; the inspected source is fine; nothing to do.
    DEGRADED  — ran; found real evidence and opened/escalated a Mission.
    UNHEALTHY — the job itself failed to run (an error inspecting), a human should look.
    """

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ExecutionResult(str, Enum):
    """What one execution did. ``ACTION_TAKEN`` means a real Mission was created/escalated."""

    OK = "ok"
    ACTION_TAKEN = "action_taken"
    ERROR = "error"


@dataclass(frozen=True)
class Observation:
    """One real finding an inspection surfaced. Never fabricated — a fact the job measured."""

    summary: str
    severity: str = "info"  # info | low | medium | high | critical
    detail: str = ""


@dataclass(frozen=True)
class MissionRequest:
    """A job's request to open a REAL Mission. Present on a ``JobResult`` ONLY with evidence
    found. ``stages`` optionally scopes the mission (e.g. a CISO job → SECURITY_REVIEW); empty lets
    the CEO planner select stages from the goal. ``escalate`` marks a threshold breach vs. routine
    action (the journal records it as MissionEscalated)."""

    goal: str
    stages: tuple[AgentCapability, ...] = ()
    escalate: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(self.stages))


@dataclass(frozen=True)
class JobResult:
    """The outcome of one job inspection. ``mission_request`` is non-None ONLY with real evidence —
    that is the no-fabrication contract, expressed in one place."""

    health: JobHealth
    summary: str
    observations: tuple[Observation, ...] = ()
    mission_request: MissionRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))

    @classmethod
    def healthy(cls, summary: str) -> JobResult:
        """The common case: inspected, all fine, nothing to do (idle — no Mission)."""
        return cls(health=JobHealth.HEALTHY, summary=summary)

    @classmethod
    def unavailable(cls, summary: str) -> JobResult:
        """The job's source (its connector) is unavailable. The job is operational and opens NO
        Mission — the unavailability shows on the connector, not as fabricated evidence here."""
        return cls(health=JobHealth.HEALTHY, summary=summary)


@dataclass(frozen=True)
class Schedule:
    """A recurring cadence. ``every_tick`` jobs (the Supervisor) run on every scheduler tick; the
    rest run when their interval has elapsed. Cadence is data, so it is fully configurable."""

    interval_seconds: float
    every_tick: bool = False

    def is_due(self, *, now: float, next_run: float | None) -> bool:
        if self.every_tick:
            return True
        return next_run is None or now >= next_run

    def next_after(self, now: float) -> float:
        return now + self.interval_seconds


@dataclass(frozen=True)
class JobContext:
    """The shared, read-only context handed to every job each tick. A job reads what it needs (the
    live ``view`` for runtime/KPI jobs, the repo for file inspections) and uses its own injected
    probe for anything external. Never carries a way to mutate the runtime."""

    now: float
    repo_root: Path
    view: RuntimeStateView | None = None


@runtime_checkable
class Job(Protocol):
    """A recurring departmental responsibility owned by an agent. Pure inspection: it declares its
    identity + cadence and turns a context into a ``JobResult``. It never opens a Mission itself —
    the scheduler does, from ``JobResult.mission_request`` — mission creation stays in one place."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def owner(self) -> AgentRole: ...

    @property
    def schedule(self) -> Schedule: ...

    @property
    def connector_id(self) -> str: ...

    def inspect(self, context: JobContext) -> JobResult: ...


class MissionGate:
    """Edge-triggers missions so a 24/7 job opens ONE Mission per problem *episode*, not one every
    tick. A job passes the current problem ``signature`` (or "" when healthy); a Mission is
    requested only when the signature changes to a new, non-empty value. An ongoing problem stays
    DEGRADED but opens no new mission; a cleared problem re-arms. This is the difference between
    surfacing real evidence once and fabricating repeated activity."""

    def __init__(self) -> None:
        self._open_problem = ""

    def evaluate(
        self,
        *,
        signature: str,
        goal: str,
        degraded_summary: str,
        healthy_summary: str,
        stages: tuple[AgentCapability, ...] = (),
        observations: tuple[Observation, ...] = (),
        escalate: bool = False,
    ) -> JobResult:
        if not signature:
            self._open_problem = ""
            return JobResult(JobHealth.HEALTHY, healthy_summary, observations)
        if signature == self._open_problem:
            return JobResult(
                JobHealth.DEGRADED, f"{degraded_summary} (ongoing)", observations
            )
        self._open_problem = signature
        return JobResult(
            JobHealth.DEGRADED,
            degraded_summary,
            observations,
            MissionRequest(goal, stages, escalate),
        )


@dataclass
class JobState:
    """The live, persisted state of one job — every field the Dashboard's Jobs panel shows. Mutated
    only by the scheduler's fold. This is the projection the snapshot serializes."""

    id: str
    name: str
    owner: AgentRole
    schedule_seconds: float
    connector_id: str = ""
    every_tick: bool = False
    enabled: bool = True
    next_run: float | None = None
    last_run: float | None = None
    last_duration_ms: float | None = None
    health: JobHealth = JobHealth.UNKNOWN
    execution_result: ExecutionResult | None = None
    created_missions: int = 0
    last_summary: str = ""
    # Accumulated only; never a constructor arg.
    last_mission_id: str | None = field(default=None, init=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "owner_agent": self.owner.value,
            "connector_id": self.connector_id,
            "schedule_seconds": self.schedule_seconds,
            "every_tick": self.every_tick,
            "enabled": self.enabled,
            "next_run": self.next_run,
            "last_run": self.last_run,
            "last_duration_ms": self.last_duration_ms,
            "health": self.health.value,
            "execution_result": (
                self.execution_result.value if self.execution_result is not None else None
            ),
            "created_missions": self.created_missions,
            "last_summary": self.last_summary,
            "last_mission_id": self.last_mission_id,
        }

    @classmethod
    def from_job(cls, job: Job) -> JobState:
        return cls(
            id=job.id,
            name=job.name,
            owner=job.owner,
            schedule_seconds=job.schedule.interval_seconds,
            connector_id=job.connector_id,
            every_tick=job.schedule.every_tick,
        )
