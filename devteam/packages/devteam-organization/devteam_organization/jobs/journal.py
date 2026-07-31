"""The jobs journal — job telemetry in the shared log dir, alongside the runtime journal.

Reuses the journaling *mechanism* (append-only JSONL + a JSON snapshot) and its *location*
(the same log directory the runtime journal and Dashboard already use). It writes SIBLING files
(``jobs.jsonl`` events, ``jobs.json`` snapshot) so it can never corrupt the frozen mission journal —
Missions a job creates still land in ``runtime.jsonl`` as normal, observed missions.

- ``jobs.jsonl`` records the lifecycle: JobStarted, JobCompleted, JobErrored, MissionCreated,
  MissionEscalated — the audit trail the spec asks for.
- ``jobs.json`` is the current state of every job (overwritten each tick) — the Dashboard's
  panel reads.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from devteam_organization.jobs.framework import JobState

_LOG = logging.getLogger("devteam.organization.jobs")


class JobEventKind(str, Enum):
    JOB_STARTED = "JobStarted"
    JOB_COMPLETED = "JobCompleted"
    JOB_ERRORED = "JobErrored"
    MISSION_CREATED = "MissionCreated"
    MISSION_ESCALATED = "MissionEscalated"


@dataclass(frozen=True)
class JobEvent:
    """One immutable job-lifecycle fact, past-tense, mirroring the runtime event model."""

    kind: JobEventKind
    occurred_at: float
    job_id: str
    name: str
    owner: str
    summary: str = ""
    health: str = ""
    duration_ms: float | None = None
    mission_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "occurred_at": self.occurred_at,
            "job_id": self.job_id,
            "name": self.name,
            "owner": self.owner,
            "summary": self.summary,
            "health": self.health,
            "duration_ms": self.duration_ms,
            "mission_id": self.mission_id,
        }


class JobJournalSink(Protocol):
    """Where job telemetry goes. A Protocol so the scheduler is testable without files."""

    def record(self, event: JobEvent) -> None: ...

    def write_snapshot(self, states: Sequence[JobState]) -> None: ...


class FileJobJournal:
    """The production sink: append events to ``jobs.jsonl``, overwrite the ``jobs.json`` snapshot.
    Best-effort — a write failure is logged and swallowed, never crashing the daemon."""

    def __init__(self, event_path: Path | str, snapshot_path: Path | str) -> None:
        self._event_path = Path(event_path)
        self._snapshot_path = Path(snapshot_path)

    def record(self, event: JobEvent) -> None:
        try:
            self._event_path.parent.mkdir(parents=True, exist_ok=True)
            with self._event_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict()) + "\n")
        except OSError:
            _LOG.exception("failed to append job event %s", event.kind.value)

    def write_snapshot(self, states: Sequence[JobState]) -> None:
        payload = {"jobs": [state.to_dict() for state in states]}
        try:
            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._snapshot_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self._snapshot_path)  # atomic swap so the Dashboard never reads a torn file
        except OSError:
            _LOG.exception("failed to write jobs snapshot")


class NullJobJournal:
    """A no-op sink for tests / unobserved runs."""

    def record(self, event: JobEvent) -> None:  # noqa: D102
        return None

    def write_snapshot(self, states: Sequence[JobState]) -> None:  # noqa: D102
        return None


def read_jobs_snapshot(path: Path | str) -> dict[str, object]:
    """Read the ``jobs.json`` snapshot for the Dashboard. A missing/torn file yields an empty roster
    (the panel shows "no jobs yet", never an error)."""
    p = Path(path)
    if not p.exists():
        return {"jobs": [], "snapshot_present": False}
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {"jobs": [], "snapshot_present": False}
    jobs = raw.get("jobs") if isinstance(raw, dict) else None
    return {"jobs": jobs if isinstance(jobs, list) else [], "snapshot_present": True}
