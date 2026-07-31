"""Read the connectors snapshot and shape it for the Connectors panel.

Presentation-only. The organization service writes ``connectors.json`` (each connector's health,
latency, last sync, status, metrics) into the shared log dir; this reads it and joins the jobs
snapshot (``jobs.json``) to attach each connector's Owner Jobs — the jobs that consume it. No
dependency on the organization runtime; a missing snapshot yields an empty roster, never an error.
"""

from __future__ import annotations

import json
from pathlib import Path

_FIELDS = (
    "id",
    "name",
    "type",
    "owner",
    "enabled",
    "health",
    "status",
    "last_check",
    "latency_ms",
    "detail",
    "metrics",
)


def read_connectors(connectors_path: Path | str, jobs_path: Path | str) -> dict[str, object]:
    """The Connectors-panel payload: each connector's state plus the Owner Jobs that consume it.
    Absent snapshot ⇒ empty roster, ``snapshot_present=False``."""
    snapshot = _read(connectors_path, "connectors")
    if snapshot is None:
        return {
            "connectors": [],
            "count": 0,
            "snapshot_present": False,
            "path": str(connectors_path),
        }
    owners = _jobs_by_connector(jobs_path)
    connectors = [_shape(row, owners) for row in snapshot if isinstance(row, dict)]
    return {
        "connectors": connectors,
        "count": len(connectors),
        "snapshot_present": True,
        "path": str(connectors_path),
    }


def _shape(row: dict[str, object], owners: dict[str, list[str]]) -> dict[str, object]:
    shaped: dict[str, object] = {field: row.get(field) for field in _FIELDS}
    connector_id = row.get("id")
    shaped["owner_jobs"] = owners.get(connector_id, []) if isinstance(connector_id, str) else []
    return shaped


def _jobs_by_connector(jobs_path: Path | str) -> dict[str, list[str]]:
    jobs = _read(jobs_path, "jobs")
    out: dict[str, list[str]] = {}
    for job in jobs or []:
        if isinstance(job, dict):
            connector_id = job.get("connector_id")
            name = job.get("name")
            if isinstance(connector_id, str) and connector_id and isinstance(name, str):
                out.setdefault(connector_id, []).append(name)
    return out


def _read(path: Path | str, key: str) -> list[object] | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    value = raw.get(key) if isinstance(raw, dict) else None
    return value if isinstance(value, list) else []
