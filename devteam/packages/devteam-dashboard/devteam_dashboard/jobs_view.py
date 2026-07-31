"""Read the AI Organization Jobs snapshot and shape it for the Jobs panel.

Presentation-only, like the rest of the dashboard. The organization service writes ``jobs.json``
(the current state of every departmental job) into the shared log dir; this reads that snapshot
directly — no dependency on the organization runtime, no runtime logic, just a read + a reshape. A
missing/torn snapshot yields an empty roster (the panel shows "no jobs yet"), never an error.
"""

from __future__ import annotations

import json
from pathlib import Path

# The fields the snapshot carries for each job; passed through to the panel plus a derived status.
_FIELDS = (
    "id",
    "name",
    "owner_agent",
    "schedule_seconds",
    "every_tick",
    "enabled",
    "next_run",
    "last_run",
    "last_duration_ms",
    "health",
    "execution_result",
    "created_missions",
    "last_summary",
    "last_mission_id",
)


def read_jobs(jobs_path: Path | str) -> dict[str, object]:
    """The Jobs-panel payload: every job's current state from the snapshot, each tagged with a
    derived display ``status``. Absent snapshot ⇒ empty roster, ``snapshot_present=False``."""
    p = Path(jobs_path)
    if not p.exists():
        return {"jobs": [], "count": 0, "snapshot_present": False, "jobs_path": str(p)}
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {"jobs": [], "count": 0, "snapshot_present": False, "jobs_path": str(p)}
    rows = raw.get("jobs") if isinstance(raw, dict) else None
    jobs = [_shape(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    return {
        "jobs": jobs,
        "count": len(jobs),
        "snapshot_present": True,
        "jobs_path": str(p),
    }


def _shape(row: dict[str, object]) -> dict[str, object]:
    shaped: dict[str, object] = {field: row.get(field) for field in _FIELDS}
    shaped["status"] = _status(row)
    return shaped


def _status(row: dict[str, object]) -> str:
    """A single display status for the panel, derived from the job's recorded state."""
    if row.get("enabled") is False:
        return "disabled"
    health = row.get("health")
    if health == "unhealthy":
        return "error"
    if health == "degraded" or row.get("execution_result") == "action_taken":
        return "acted"
    if row.get("last_run") is None:
        return "pending"
    return "idle"
