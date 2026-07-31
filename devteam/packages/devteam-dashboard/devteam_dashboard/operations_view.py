"""Read the single Operations Projection the daemon writes — the ONLY source this view reads (S6).

The daemon folds every live object (problems, approvals, missions, metrics, activity) into one
``operations.json``; this returns it verbatim. The dashboard never merges sources of its own — it is
a pure Viewer over the projection (``Core -> Projection -> Viewer``). An absent snapshot yields an
empty-but-shaped view with ``snapshot_present=False``.
"""

from __future__ import annotations

import json
from pathlib import Path

_SECTIONS = (
    "active_problems",
    "pending_approvals",
    "running_missions",
    "escalations",
    "recent_activity",
)


def read_operations(path: Path | str) -> dict[str, object]:
    """The whole OperationsSnapshot as the daemon wrote it, plus ``snapshot_present``/``path``."""
    raw = _read(path)
    if raw is None:
        return _empty(path)
    view = dict(raw)
    view["snapshot_present"] = True
    view["path"] = str(path)
    return view


def _read(path: Path | str) -> dict[str, object] | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) else None


def _empty(path: Path | str) -> dict[str, object]:
    view: dict[str, object] = {
        "generated_at": None,
        "health": {"status": "unknown", "detail": "no snapshot yet"},
        "metrics": {},
        "snapshot_present": False,
        "path": str(path),
    }
    for section in _SECTIONS:
        view[section] = []
    return view
