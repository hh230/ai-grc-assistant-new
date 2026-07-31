"""The Operations Projection — the ONE snapshot the daemon produces for the Viewer (S6).

The daemon holds every live object (the coordinator + ledger, the approval service, the runtime, the
metrics, an activity log); it folds them into a single ``OperationsSnapshot`` and writes
``operations.json``. The dashboard reads ONLY that snapshot — it never learns what Correlation,
Approval, Mission, or Ledger are (``Core -> Projection -> Viewer``). Each lens (approvals, missions,
activity) is a *section of this projection*, not a reader of its store.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from devteam_approval import ApprovalRequest

from devteam_organization.lifecycle import (
    LifecycleMetricsSnapshot,
    ProblemRecord,
    ProblemState,
)


@dataclass(frozen=True)
class HealthView:
    status: str  # healthy | degraded | down
    detail: str = ""


@dataclass(frozen=True)
class MetricsView:
    active_problems: int
    mean_time_to_verify: float | None
    mean_time_to_close: float | None
    retry_count: int
    escalation_count: int
    verification_failures: int
    events_processed: int
    mean_event_latency_ms: float | None

    @classmethod
    def from_snapshot(cls, snap: LifecycleMetricsSnapshot) -> MetricsView:
        return cls(
            active_problems=snap.active_problems,
            mean_time_to_verify=snap.mean_time_to_verify,
            mean_time_to_close=snap.mean_time_to_close,
            retry_count=snap.retry_count,
            escalation_count=snap.escalation_count,
            verification_failures=snap.verification_failures,
            events_processed=snap.events_processed,
            mean_event_latency_ms=snap.mean_event_latency_ms,
        )


def _split(target_ref: str) -> tuple[str, str]:
    """``mission_type:asset:signature`` -> (mission_type, asset), for display."""
    mission_type, _, rest = target_ref.partition(":")
    return mission_type, rest.partition(":")[0]


@dataclass(frozen=True)
class ProblemView:
    correlation_ref: str
    mission_type: str
    asset: str
    state: str
    severity: str
    summary: str
    first_seen: float
    last_seen: float

    @classmethod
    def from_record(cls, record: ProblemRecord) -> ProblemView:
        signal = record.signal
        return cls(
            correlation_ref=signal.correlation_ref,
            mission_type=signal.mission_type,
            asset=signal.asset,
            state=record.state.value,
            severity=signal.severity.value,
            summary=signal.summary,
            first_seen=record.first_seen,
            last_seen=record.last_seen,
        )


@dataclass(frozen=True)
class PendingApprovalView:
    id: str
    target: str
    mission_type: str
    asset: str
    role: str
    reason: str
    requirement: str
    waiting_since: float
    expires_at: float

    @classmethod
    def from_request(cls, request: ApprovalRequest) -> PendingApprovalView:
        mission_type, asset = _split(request.target_ref)
        return cls(
            id=request.id,
            target=request.target_ref,
            mission_type=mission_type,
            asset=asset,
            role=request.policy.required_role,
            reason=request.policy.reason,
            requirement=request.policy.requirement,
            waiting_since=request.created_at,
            expires_at=request.expires_at,
        )


@dataclass(frozen=True)
class MissionView:
    id: str
    goal: str
    status: str
    correlation_ref: str = ""


@dataclass(frozen=True)
class EscalationView:
    correlation_ref: str
    tier: str
    at: float


@dataclass(frozen=True)
class ActivityEvent:
    at: float
    # detected | approval_requested | approved | rejected | mission_started | verified | closed |
    # escalated
    kind: str
    ref: str
    detail: str = ""


@dataclass(frozen=True)
class OperationsSnapshot:
    generated_at: float
    health: HealthView
    metrics: MetricsView
    active_problems: tuple[ProblemView, ...]
    pending_approvals: tuple[PendingApprovalView, ...]
    running_missions: tuple[MissionView, ...]
    escalations: tuple[EscalationView, ...]
    recent_activity: tuple[ActivityEvent, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "health": asdict(self.health),
            "metrics": asdict(self.metrics),
            "active_problems": [asdict(p) for p in self.active_problems],
            "pending_approvals": [asdict(a) for a in self.pending_approvals],
            "running_missions": [asdict(m) for m in self.running_missions],
            "escalations": [asdict(e) for e in self.escalations],
            "recent_activity": [asdict(a) for a in self.recent_activity],
        }


class ActivityLog:
    """A bounded, in-order log of operator-facing events. The daemon records into it; the projection
    reads it (newest last). It replaces reading raw logs — the timeline is data, not text."""

    def __init__(self, capacity: int = 50) -> None:
        self._events: deque[ActivityEvent] = deque(maxlen=capacity)

    def record(self, kind: str, ref: str, *, at: float, detail: str = "") -> None:
        self._events.append(ActivityEvent(at=at, kind=kind, ref=ref, detail=detail))

    def events(self) -> tuple[ActivityEvent, ...]:
        return tuple(self._events)

    def restore(self, events: Iterable[ActivityEvent]) -> None:
        """Rebuild the log from a persisted snapshot on startup (the timeline survives restart)."""
        for event in events:
            self._events.append(event)


def build_operations_snapshot(
    *,
    now: float,
    health: HealthView,
    metrics: LifecycleMetricsSnapshot,
    problems: Iterable[ProblemRecord],
    pending: Iterable[ApprovalRequest],
    missions: Iterable[MissionView],
    activity: Iterable[ActivityEvent],
) -> OperationsSnapshot:
    """Fold the daemon's live objects into one snapshot. Escalations derive from the problems that
    are already in the ESCALATED state — no separate source."""
    records = list(problems)
    escalations = tuple(
        EscalationView(record.signal.correlation_ref, "escalated", record.last_seen)
        for record in records
        if record.state is ProblemState.ESCALATED
    )
    return OperationsSnapshot(
        generated_at=now,
        health=health,
        metrics=MetricsView.from_snapshot(metrics),
        active_problems=tuple(ProblemView.from_record(r) for r in records),
        pending_approvals=tuple(PendingApprovalView.from_request(r) for r in pending),
        running_missions=tuple(missions),
        escalations=escalations,
        recent_activity=tuple(activity),
    )


def write_operations_snapshot(snapshot: OperationsSnapshot, path: Path) -> None:
    """Write operations.json atomically — the single artifact the Viewer reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(snapshot.to_dict(), indent=2))
    tmp.replace(path)
