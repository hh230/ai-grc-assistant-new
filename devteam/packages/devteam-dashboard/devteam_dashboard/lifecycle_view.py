"""Read the lifecycle snapshot and shape it for the Lifecycle panel.

Presentation-only. The organization service writes ``lifecycle.json`` (the ProblemLedger's problems
+ the LifecycleMetrics snapshot) into the shared log dir; this reads it. The LifecycleCoordinator is
the single source of truth — a read-only projection; a missing snapshot yields an empty view.
"""

from __future__ import annotations

import json
from pathlib import Path

_METRIC_FIELDS = (
    "active_problems",
    "mean_time_to_verify",
    "mean_time_to_close",
    "retry_count",
    "escalation_count",
    "verification_failures",
)


def read_lifecycle(path: Path | str) -> dict[str, object]:
    """The Lifecycle-panel payload: every active problem (state + identity) plus the metrics.
    Absent snapshot ⇒ empty view, ``snapshot_present=False``."""
    raw = _read(path)
    if raw is None:
        return _empty(path)
    problems = [item for item in _list(raw.get("problems")) if isinstance(item, dict)]
    metrics_raw = raw.get("metrics")
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    return {
        "problems": problems,
        "metrics": {field: metrics.get(field) for field in _METRIC_FIELDS},
        "count": len(problems),
        "snapshot_present": True,
        "path": str(path),
    }


def _read(path: Path | str) -> dict[str, object] | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) else None


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _empty(path: Path | str) -> dict[str, object]:
    return {
        "problems": [],
        "metrics": dict.fromkeys(_METRIC_FIELDS),
        "count": 0,
        "snapshot_present": False,
        "path": str(path),
    }
