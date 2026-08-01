"""The connectors snapshot — current connector state for the Dashboard's Connectors panel.

Mirrors the jobs snapshot: the service writes ``connectors.json`` (health, latency, status,
metrics per connector) into the shared log dir; the Dashboard reads it. Presentation transport only.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

from devteam_organization.connectors.framework import ConnectorState

_LOG = logging.getLogger("devteam.organization.connectors")


def write_connectors_snapshot(states: Sequence[ConnectorState], path: Path | str) -> None:
    """Overwrite ``connectors.json`` with every connector's current state. Best-effort — a write
    failure is logged and swallowed so connector telemetry never crashes the daemon."""
    payload = {"connectors": [state.to_dict() for state in states]}
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(target)  # atomic swap so the Dashboard never reads a torn file
    except OSError:
        _LOG.exception("failed to write connectors snapshot")


def read_connectors_snapshot(path: Path | str) -> dict[str, object]:
    """Read ``connectors.json`` for the Dashboard. Missing/torn ⇒ empty roster, never an error."""
    p = Path(path)
    if not p.exists():
        return {"connectors": [], "snapshot_present": False}
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {"connectors": [], "snapshot_present": False}
    connectors = raw.get("connectors") if isinstance(raw, dict) else None
    return {
        "connectors": connectors if isinstance(connectors, list) else [],
        "snapshot_present": True,
    }
