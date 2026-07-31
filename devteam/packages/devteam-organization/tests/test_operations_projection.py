"""The Operations Projection (S6) — one snapshot folded from the daemon's live objects.

The dashboard reads only this. These lock the section mapping (problems / pending approvals /
missions / escalations / activity), the ESCALATED-derived escalations, and the atomic JSON write.
"""

from __future__ import annotations

import json
from pathlib import Path

from devteam_approval import ApprovalPolicy, ApprovalRequest
from devteam_organization.lifecycle import (
    LifecycleMetricsSnapshot,
    ProblemRecord,
    ProblemSignal,
    ProblemState,
    Severity,
)
from devteam_organization.operations_projection import (
    ActivityLog,
    HealthView,
    MissionView,
    build_operations_snapshot,
    write_operations_snapshot,
)


def _record(state: ProblemState, asset: str = "host-a") -> ProblemRecord:
    signal = ProblemSignal(
        mission_type="security",
        asset=asset,
        evidence_signature="missing_header",
        goal="g",
        summary="missing header",
        severity=Severity.HIGH,
    )
    return ProblemRecord(signal=signal, state=state, first_seen=1000.0, last_seen=1100.0)


def _metrics() -> LifecycleMetricsSnapshot:
    return LifecycleMetricsSnapshot(
        active_problems=2,
        mean_time_to_verify=10.0,
        mean_time_to_close=20.0,
        retry_count=1,
        escalation_count=1,
        verification_failures=0,
        events_processed=3,
        mean_event_latency_ms=5.0,
    )


def _pending() -> ApprovalRequest:
    return ApprovalRequest(
        id="apr_1",
        target_ref="operations:site.example:endpoint_down",
        resume_token="t",
        policy=ApprovalPolicy("standard", "ops_owner", "site is down"),
        created_at=1050.0,
    )


def test_snapshot_folds_every_section() -> None:
    activity = ActivityLog()
    activity.record("detected", "security:host-a:missing_header", at=1000.0, detail="x")
    snap = build_operations_snapshot(
        now=1200.0,
        health=HealthView("healthy"),
        metrics=_metrics(),
        problems=[
            _record(ProblemState.IN_PROGRESS),
            _record(ProblemState.ESCALATED, asset="host-b"),
        ],
        pending=[_pending()],
        missions=[MissionView("m1", "restart", "running", "operations:site.example:endpoint_down")],
        activity=activity.events(),
    )

    assert snap.generated_at == 1200.0
    assert len(snap.active_problems) == 2
    # escalations are DERIVED from problems already in the ESCALATED state — no separate source
    assert [e.correlation_ref for e in snap.escalations] == ["security:host-b:missing_header"]
    approval = snap.pending_approvals[0]
    assert approval.mission_type == "operations" and approval.asset == "site.example"
    assert approval.role == "ops_owner" and approval.waiting_since == 1050.0
    assert snap.running_missions[0].id == "m1"
    assert snap.recent_activity[0].kind == "detected"
    assert set(snap.to_dict()) == {
        "generated_at", "health", "metrics", "active_problems", "pending_approvals",
        "running_missions", "escalations", "recent_activity",
    }


def test_write_is_atomic_and_reads_back(tmp_path: Path) -> None:
    snap = build_operations_snapshot(
        now=1.0, health=HealthView("down", "worker down"), metrics=_metrics(),
        problems=[], pending=[], missions=[], activity=[],
    )
    path = tmp_path / "operations.json"
    write_operations_snapshot(snap, path)
    data = json.loads(path.read_text())
    assert data["health"] == {"status": "down", "detail": "worker down"}
    assert data["metrics"]["active_problems"] == 2 and data["pending_approvals"] == []


def test_activity_log_is_bounded_newest_last() -> None:
    log = ActivityLog(capacity=3)
    for i in range(5):
        log.record("closed", f"r{i}", at=float(i))
    events = log.events()
    assert len(events) == 3 and events[0].ref == "r2" and events[-1].ref == "r4"
