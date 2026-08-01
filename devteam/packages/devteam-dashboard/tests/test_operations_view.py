"""The Operations view (S6) — reads the ONE projection verbatim, merges nothing.

Absent snapshot ⇒ empty-but-shaped view. Present ⇒ the daemon's snapshot returned as-is.
"""

from __future__ import annotations

import json
from pathlib import Path

from devteam_dashboard.operations_view import read_operations


def test_absent_snapshot_is_empty_but_shaped(tmp_path: Path) -> None:
    view = read_operations(tmp_path / "operations.json")
    assert view["snapshot_present"] is False
    assert view["health"] == {"status": "unknown", "detail": "no snapshot yet"}
    for section in ("active_problems", "pending_approvals", "running_missions", "recent_activity"):
        assert view[section] == []


def test_present_snapshot_is_returned_verbatim(tmp_path: Path) -> None:
    path = tmp_path / "operations.json"
    snapshot = {
        "generated_at": 1785500000.0,
        "health": {"status": "healthy", "detail": ""},
        "metrics": {"active_problems": 1, "mean_time_to_close": 158.9},
        "active_problems": [{"correlation_ref": "operations:site:endpoint_down", "state": "new"}],
        "pending_approvals": [{"id": "apr_1", "target": "operations:site:endpoint_down"}],
        "running_missions": [{"id": "m1", "status": "running"}],
        "escalations": [],
        "recent_activity": [{"at": 1785500000.0, "kind": "detected", "ref": "operations:site"}],
    }
    path.write_text(json.dumps(snapshot))

    view = read_operations(path)
    assert view["snapshot_present"] is True
    assert view["metrics"] == {"active_problems": 1, "mean_time_to_close": 158.9}
    approvals = view["pending_approvals"]
    activity = view["recent_activity"]
    assert isinstance(approvals, list) and approvals[0]["id"] == "apr_1"
    assert isinstance(activity, list) and activity[0]["kind"] == "detected"
