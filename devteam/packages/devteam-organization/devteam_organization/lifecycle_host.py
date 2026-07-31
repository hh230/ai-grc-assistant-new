"""The daemon-side host for the lifecycle engine (ADR 0065, S4b-2b-2b Parts B–E).

This is the org's composition root for the *running* system: it supplies the real leaf primitives —
read a connector (``use_cache=False``), verify against the runtime, open/check/escalate a mission
through ``OrganizationRuntime`` — and hands them to ``build_lifecycle``. It also persists the
coordinator's state + metrics to a snapshot and recovers from it on startup.

The relationship is one-way (Daemon → Lifecycle): the lifecycle package imports nothing from here;
this module imports the lifecycle + the runtime and wires them. Every transition is logged so the
live logs show a problem moving between states, and every problem's state is the coordinator's alone
— the snapshot is a read-only projection of it (single source of truth).
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from devteam_approval import (
    ApprovalPolicy as DomainApprovalPolicy,
)
from devteam_approval import (
    ApprovalService,
    ApprovalStatus,
    FileApprovalStore,
)
from devteam_contracts import platform_tenant
from devteam_protocol import AgentCapability
from mission_engine.lifecycle import is_terminal as _status_is_terminal

from devteam_organization.approval_adapter import ApprovalDecisionAdapter
from devteam_organization.connectors import ConnectorRegistry
from devteam_organization.lifecycle import (
    AdapterRegistry,
    Evidence,
    EvidenceState,
    LifecycleComposition,
    ProblemRecord,
    ProblemSignal,
    ProblemState,
    RemediationPlan,
    Severity,
    Transition,
    build_evidence_sources,
    build_lifecycle,
)
from devteam_organization.operations_projection import (
    ActivityEvent,
    ActivityLog,
    HealthView,
    MissionView,
    OperationsSnapshot,
    build_operations_snapshot,
)
from devteam_organization.runtime import OrganizationRuntime

# Where the shared approval store lives — the Approval API writes here, the daemon reads here (the
# file-store + reconcile design). Matches devteam_approval_api.config so both default to one file.
_DEFAULT_APPROVAL_STORE = Path.home() / ".rasheed" / "approvals.json"

# Mission statuses that mean "no longer running" — filtered out of the projection's running list.
_TERMINAL_MISSIONS = frozenset({"completed", "failed", "cancelled", "archived", "done"})

# The mission a remediation opens once approved (a gated step returns None until then).
OpenNow = Callable[[ProblemSignal, RemediationPlan, int], str]
OpenMission = Callable[[ProblemSignal, RemediationPlan, int], "str | None"]

_LOG = logging.getLogger("devteam.organization.lifecycle")

# Remediation missions run the CEO's decision + the DevTeam's delivery plan; landing stays gated
# through the squad's fix-it flow (ADR 0044). The lifecycle owns the problem; the mission is work.
_REMEDIATION_STAGES = [AgentCapability.STRATEGY, AgentCapability.DELIVERY]


def _str_list(data: Mapping[str, object], key: str) -> list[str]:
    value = data.get(key)
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _approval_store_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    raw = os.environ.get("RASHEED_APPROVAL_STORE", "").strip()
    return Path(raw) if raw else _DEFAULT_APPROVAL_STORE


def _approval_policy(signal: ProblemSignal, plan: RemediationPlan) -> DomainApprovalPolicy:
    """Map the lifecycle Strategy's approval → the Approval Domain's policy, composing a
    human-readable reason (the problem summary + why the gate exists) for the UI."""
    gate = plan.approval
    context = signal.summary or signal.goal or signal.correlation_ref
    reason = f"{context} — {gate.reason}" if gate.reason else context
    return DomainApprovalPolicy(
        requirement=gate.requirement.value,
        required_role=gate.approver,
        reason=reason,
    )


def build_approval_gate(
    approvals: ApprovalService,
    open_now: OpenNow,
    *,
    on_request: Callable[[ProblemSignal, DomainApprovalPolicy], None] | None = None,
) -> OpenMission:
    """Turn the mission-opening seam into a human gate (no Core change — this is the host seam). A
    non-consequential remediation opens immediately. A consequential one opens a pending
    ApprovalRequest and returns None (the driver stays PENDING → the problem waits) until a human
    GRANTS it; then the mission opens. REJECTED / EXPIRED / CANCELLED never open. One grant covers
    the remediation incl. its retries to the cap; the request is cleared when the problem closes, so
    a recurrence re-gates. ``on_request`` fires once when a gate is first opened (for the activity
    log)."""

    def open_mission(signal: ProblemSignal, plan: RemediationPlan, number: int) -> str | None:
        if not plan.consequential:
            return open_now(signal, plan, number)
        ref = signal.correlation_ref
        request = approvals.for_target(ref)
        if request is None:
            policy = _approval_policy(signal, plan)
            approvals.create(target_ref=ref, resume_token=ref, policy=policy)
            _LOG.info("lifecycle: gate opened — awaiting approval for %s", ref)
            if on_request is not None:
                on_request(signal, policy)
            return None
        if request.status is ApprovalStatus.GRANTED:
            return open_now(signal, plan, number)
        return None  # pending / rejected / expired / cancelled → do not execute

    return open_mission


_ACTIVITY_BY_STATE: dict[ProblemState, str] = {
    ProblemState.NEW: "detected",
    ProblemState.VERIFIED: "verified",
    ProblemState.CLOSED: "closed",
    ProblemState.ESCALATED: "escalated",
}


def _record_activity(
    activity: ActivityLog, transition: Transition, approvals: ApprovalService
) -> None:
    """Fold a lifecycle transition into operator-facing activity. An approval-driven resume records
    both 'approved (by role)' and 'mission started', so the timeline reads as a human narrative."""
    ref = transition.correlation_ref
    at = transition.at
    if transition.to_state is ProblemState.IN_PROGRESS:
        if transition.source == "approval":
            request = approvals.for_target(ref)
            role = ""
            if request is not None and request.current_decision is not None:
                actor = request.current_decision.actor
                role = actor.role or actor.actor_id
            activity.record("approved", ref, at=at, detail=f"by {role}" if role else "human")
        activity.record("mission_started", ref, at=at, detail=transition.reason)
        return
    kind = _ACTIVITY_BY_STATE.get(transition.to_state)
    if kind is not None:
        activity.record(kind, ref, at=at, detail=transition.reason)


@dataclass
class OrganizationLifecycle:
    """The daemon's handle on the running lifecycle: the composition it syncs, plus the single
    OperationsSnapshot it projects. The daemon hosts this; the dashboard never sees it — only the
    snapshot written to operations.json (Core -> Projection -> Viewer)."""

    composition: LifecycleComposition
    approvals: ApprovalService
    activity: ActivityLog
    runtime: OrganizationRuntime
    registry: ConnectorRegistry

    def sync(self) -> None:
        self.composition.sync()

    def snapshot(self, *, now: float) -> OperationsSnapshot:
        return build_operations_snapshot(
            now=now,
            health=self._health(),
            metrics=self.composition.metrics_snapshot(),
            problems=self.composition.coordinator.export(),
            pending=self.approvals.pending(),
            missions=self._missions(),
            activity=self.activity.events(),
        )

    def _health(self) -> HealthView:
        result = self.registry.fetch("runtime", use_cache=True)
        if not result.available:
            return HealthView("degraded", "runtime connector unavailable")
        down = _str_list(result.data, "workers_down")
        stalled = _str_list(result.data, "stalled_agents")
        if down:
            return HealthView("down", f"{len(down)} worker(s) down")
        if stalled:
            return HealthView("degraded", f"{len(stalled)} agent(s) stalled")
        return HealthView("healthy")

    def _missions(self) -> list[MissionView]:
        running: list[MissionView] = []
        for mission in self.runtime.view.missions():
            status = str(mission.get("status", ""))
            if status in _TERMINAL_MISSIONS:
                continue
            running.append(
                MissionView(
                    id=str(mission.get("mission_id", "")),
                    goal=str(mission.get("owner", "")),
                    status=status,
                )
            )
        return running


def build_organization_lifecycle(
    runtime: OrganizationRuntime,
    registry: ConnectorRegistry,
    *,
    approval_store_path: Path | None = None,
    clock: Callable[[], float] = time.time,
) -> OrganizationLifecycle:
    """Assemble the live lifecycle engine over the real runtime + connectors, gated by human
    approval: consequential remediations wait for a decision recorded via the Approval API, which a
    registered ``ApprovalDecisionAdapter`` drains into the coordinator each pass (no Core edit).
    Returns the daemon's handle — the composition plus the OperationsSnapshot it projects (S6)."""
    tenant = platform_tenant("org-lifecycle")
    approvals = ApprovalService(FileApprovalStore(_approval_store_path(approval_store_path)))
    activity = ActivityLog()

    def connector_data(connector_id: str) -> Mapping[str, object] | None:
        result = registry.fetch(connector_id, use_cache=False)
        return result.data if result.available else None

    def runtime_healthy(_signal: ProblemSignal) -> Evidence:
        result = registry.fetch("runtime", use_cache=False)
        if not result.available:
            return Evidence.unavailable("runtime", "runtime connector unavailable")
        down = _str_list(result.data, "workers_down")
        stalled = _str_list(result.data, "stalled_agents")
        if down or stalled:
            return Evidence("runtime", EvidenceState.UNSATISFIED, "runtime unhealthy")
        return Evidence("runtime", EvidenceState.SATISFIED, "runtime healthy")

    def open_now(signal: ProblemSignal, plan: RemediationPlan, number: int) -> str:
        goal = f"{plan.instruction} [{signal.correlation_ref} · attempt {number}]"
        mission = runtime.run_mission(goal, stages=list(_REMEDIATION_STAGES))
        _LOG.info("lifecycle: opened mission %s for %s", mission.id, signal.correlation_ref)
        return mission.id

    def on_gate(signal: ProblemSignal, policy: DomainApprovalPolicy) -> None:
        activity.record(
            "approval_requested", signal.correlation_ref, at=clock(), detail=policy.reason
        )

    open_mission = build_approval_gate(approvals, open_now, on_request=on_gate)

    def is_terminal(mission_id: str) -> bool:
        try:
            mission = runtime.engine.get(mission_id, tenant)
        except Exception:  # unknown id (e.g. a prior process) → treat as finished, never block
            return True
        return _status_is_terminal(mission.status)

    def escalate_mission(problem: object, tier: object, alert: object) -> None:
        reason = getattr(alert, "reason", str(alert))
        goal = f"ESCALATION [{tier}] {reason}"
        mission = runtime.run_mission(goal, stages=[AgentCapability.STRATEGY])
        _LOG.warning("lifecycle: escalated to %s via mission %s", tier, mission.id)

    def on_transition(transition: Transition) -> None:
        _LOG.info(
            "lifecycle: %s  %s → %s  (%s; %s/%s)",
            transition.correlation_ref,
            transition.from_state.value if transition.from_state is not None else "—",
            transition.to_state.value,
            transition.reason,
            transition.trigger.value,
            transition.source or "?",
        )
        _record_activity(activity, transition, approvals)
        if transition.to_state is ProblemState.CLOSED:
            # The gate is done; clear it so a later recurrence of this problem opens a fresh one.
            approvals.clear_target(transition.correlation_ref)

    adapters = AdapterRegistry()
    adapters.register(ApprovalDecisionAdapter(approvals))
    evidence = build_evidence_sources(
        connector_fetch=connector_data, runtime_healthy=runtime_healthy
    )
    composition = build_lifecycle(
        connector_data=connector_data,
        evidence=evidence,
        open_mission=open_mission,
        is_terminal=is_terminal,
        escalate_mission=escalate_mission,
        adapters=adapters,
        on_transition=on_transition,
        clock=clock,
    )
    return OrganizationLifecycle(composition, approvals, activity, runtime, registry)


def write_lifecycle_snapshot(composition: LifecycleComposition, path: Path) -> None:
    """Persist the coordinator's state + metrics — a read-only projection the dashboard reads, and
    what the daemon recovers from. The coordinator remains the single source of truth."""
    snap = composition.metrics_snapshot()
    payload = {
        "problems": [_record_to_dict(record) for record in composition.coordinator.export()],
        "metrics": {
            "active_problems": snap.active_problems,
            "mean_time_to_verify": snap.mean_time_to_verify,
            "mean_time_to_close": snap.mean_time_to_close,
            "retry_count": snap.retry_count,
            "escalation_count": snap.escalation_count,
            "verification_failures": snap.verification_failures,
        },
        "metrics_state": composition.metrics.export(),  # for cross-restart metric continuity
    }
    path.write_text(json.dumps(payload, indent=2))


def recover_lifecycle(composition: LifecycleComposition, path: Path) -> int:
    """Rebuild the coordinator's state from the snapshot on startup. Returns how many problems were
    recovered — so the daemon continues in-flight problems instead of restarting from zero."""
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0
    problems = payload.get("problems", []) if isinstance(payload, dict) else []
    records = [_dict_to_record(item) for item in problems if isinstance(item, dict)]
    composition.coordinator.recover(records)
    metrics_state = payload.get("metrics_state") if isinstance(payload, dict) else None
    if isinstance(metrics_state, dict):
        composition.metrics.restore(metrics_state)  # active count + mean-times survive the restart
    return len(records)


def recover_activity(activity: ActivityLog, path: Path) -> int:
    """Rebuild the operator's activity timeline from the last operations snapshot on startup (AR-1).
    ``recent_activity`` already lives in ``operations.json``; this restores it so a restart does not
    empty the timeline. Host-only — no Core, contract, state, or dependency change. Returns the
    count restored; a missing/corrupt snapshot restores nothing (the timeline simply refills)."""
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0
    rows = payload.get("recent_activity", []) if isinstance(payload, dict) else []
    events = [_dict_to_activity(row) for row in rows if isinstance(row, dict)]
    activity.restore(events)
    return len(events)


def _dict_to_activity(row: dict[str, object]) -> ActivityEvent:
    return ActivityEvent(
        at=float(row.get("at", 0.0)),  # type: ignore[arg-type]
        kind=str(row.get("kind", "")),
        ref=str(row.get("ref", "")),
        detail=str(row.get("detail", "")),
    )


def _record_to_dict(record: ProblemRecord) -> dict[str, object]:
    signal = record.signal
    return {
        "correlation_ref": signal.correlation_ref,
        "mission_type": signal.mission_type,
        "asset": signal.asset,
        "evidence_signature": signal.evidence_signature,
        "connector_id": signal.connector_id,
        "severity": signal.severity.value,
        "goal": signal.goal,
        "summary": signal.summary,
        "state": record.state.value,
        "first_seen": record.first_seen,
        "last_seen": record.last_seen,
    }


def _dict_to_record(item: dict[str, object]) -> ProblemRecord:
    signal = ProblemSignal(
        mission_type=str(item.get("mission_type", "")),
        asset=str(item.get("asset", "")),
        evidence_signature=str(item.get("evidence_signature", "")),
        goal=str(item.get("goal", "")),
        summary=str(item.get("summary", "")),
        severity=Severity(str(item.get("severity", "medium"))),
        connector_id=str(item.get("connector_id", "")),
    )
    return ProblemRecord(
        signal=signal,
        state=ProblemState(str(item.get("state", "new"))),
        first_seen=float(item.get("first_seen", 0.0)),  # type: ignore[arg-type]
        last_seen=float(item.get("last_seen", 0.0)),  # type: ignore[arg-type]
    )
