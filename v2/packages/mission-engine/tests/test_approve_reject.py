"""Slice 2 of the Human Approval lifecycle (ADR 0044): the aggregate can *resolve* a pending gate.
`approve()` drives AWAITING_APPROVAL → RESUMED and `reject()` → CANCELLED, each recording an
`ApprovalDecision`. Lifecycle only: **no** resume orchestration, no engine emission,
no RBAC (the aggregate re-checks tenant and records the approver as data only).

The two decision events (`MissionApproved` / `MissionRejected`) are defined and registered in
Slice 2 (their shape is locked here); the engine that *emits* them is a later slice.
"""

from __future__ import annotations

import pytest
from mission_engine import (
    ApprovalError,
    ApprovalRequest,
    Mission,
    MissionApproved,
    MissionRejected,
    MissionStatus,
    Plan,
    PlanStep,
    TenantMismatch,
)
from pipeline_contracts import TenantContext


def _paused_mission(tenant: TenantContext) -> Mission:
    """A mission paused at a gate: EXECUTING → AWAITING_APPROVAL with a pending ApprovalRequest."""
    mission = Mission.create(goal="draft an access-control policy", tenant=tenant)
    mission.set_plan(
        Plan(steps=(PlanStep(description="author", instruction="write", consequential=True),))
    )
    mission.begin_execution()
    mission.await_approval(
        ApprovalRequest(reason="writes a policy", requested_by="mission", requested_at=1.0)
    )
    return mission


# ── approve ───────────────────────────────────────────────────────────────────
def test_approve_moves_to_resumed_and_records_the_decision(tenant: TenantContext) -> None:
    mission = _paused_mission(tenant)
    request_id = mission.approval.id if mission.approval else ""

    mission.approve(tenant, comment="looks good", now=5.0)

    assert mission.status is MissionStatus.RESUMED
    assert mission.approval is not None
    decision = mission.approval.decision
    assert decision is not None
    assert decision.approved is True
    assert decision.approver == tenant.principal_id  # recorded as data, not authorized here
    assert decision.comment == "looks good"
    assert decision.decided_at == 5.0
    assert mission.approval.id == request_id  # same request, now carrying its decision
    assert not mission.has_active_approval  # decided → no longer active


def test_approve_does_not_resume_execution(tenant: TenantContext) -> None:
    """Slice 2 is a pure state transition: approve lands the mission in RESUMED and stops. It does
    NOT re-enter EXECUTING or run the gated step — that orchestration is a later slice."""
    mission = _paused_mission(tenant)
    mission.approve(tenant)
    assert mission.status is MissionStatus.RESUMED
    assert not mission.step_results  # nothing executed


# ── reject ────────────────────────────────────────────────────────────────────
def test_reject_moves_to_cancelled_and_records_the_decision(tenant: TenantContext) -> None:
    mission = _paused_mission(tenant)

    mission.reject(tenant, comment="insufficient evidence", now=7.0)

    assert mission.status is MissionStatus.CANCELLED
    assert mission.is_terminal  # a rejection stops the mission fail-safe (reuses CANCELLED)
    decision = mission.approval.decision if mission.approval else None
    assert decision is not None
    assert decision.approved is False
    assert decision.approver == tenant.principal_id
    assert decision.comment == "insufficient evidence"
    assert decision.decided_at == 7.0
    assert not mission.has_active_approval


# ── tenant re-check (ADR 0040 §5) ─────────────────────────────────────────────
def test_approve_by_a_foreign_tenant_is_refused(
    tenant: TenantContext, other_tenant: TenantContext
) -> None:
    mission = _paused_mission(tenant)
    with pytest.raises(TenantMismatch):
        mission.approve(other_tenant)
    # unchanged: still paused, still pending
    assert mission.status is MissionStatus.AWAITING_APPROVAL
    assert mission.has_active_approval
    assert mission.approval is not None and mission.approval.decision is None


def test_reject_by_a_foreign_tenant_is_refused(
    tenant: TenantContext, other_tenant: TenantContext
) -> None:
    mission = _paused_mission(tenant)
    with pytest.raises(TenantMismatch):
        mission.reject(other_tenant)
    assert mission.status is MissionStatus.AWAITING_APPROVAL
    assert mission.has_active_approval


# ── no pending request / wrong state ──────────────────────────────────────────
def test_cannot_approve_without_a_pending_request(tenant: TenantContext) -> None:
    mission = Mission.create(goal="g", tenant=tenant)  # CREATED, no gate
    with pytest.raises(ApprovalError, match="no pending approval"):
        mission.approve(tenant)


def test_cannot_decide_twice(tenant: TenantContext) -> None:
    """After a decision the request is no longer active, so a second approve/reject is refused —
    a gate is resolved exactly once."""
    mission = _paused_mission(tenant)
    mission.approve(tenant)
    with pytest.raises(ApprovalError, match="no pending approval"):
        mission.approve(tenant)


def test_illegal_transition_leaves_the_request_undecided(tenant: TenantContext) -> None:
    """A pending request in the wrong state (white-box: EXECUTING) cannot be approved — the
    transition is validated BEFORE the decision is written, so the frozen request is never left
    half-decided."""
    pending = ApprovalRequest(reason="r", requested_by="mission", requested_at=1.0)
    mission = Mission(
        id="mis_x",
        tenant=tenant,
        goal="g",
        trace_id="trc_x",
        status=MissionStatus.EXECUTING,  # not AWAITING_APPROVAL
        approval=pending,
        created_at=1.0,
        updated_at=1.0,
    )
    from mission_engine import IllegalTransition

    with pytest.raises(IllegalTransition):
        mission.approve(tenant)
    assert mission.status is MissionStatus.EXECUTING
    assert mission.approval is pending and mission.approval.decision is None  # untouched


# ── the decision events' shape (defined + locked in Slice 2) ──────────────────
def test_mission_approved_event_payload() -> None:
    event = MissionApproved(
        trace_id="trc_1",
        tenant_id="org_acme",
        mission_id="mis_1",
        occurred_at=5.0,
        approval_id="apr_1",
        approver="u_owner",
    )
    assert event.name == "mission.approved"
    payload = event.to_dict()
    assert payload["approval_id"] == "apr_1"
    assert payload["approver"] == "u_owner"
    assert payload["mission_id"] == "mis_1"
    assert payload["tenant_id"] == "org_acme"


def test_mission_rejected_event_payload() -> None:
    event = MissionRejected(
        trace_id="trc_1",
        tenant_id="org_acme",
        mission_id="mis_1",
        occurred_at=7.0,
        approval_id="apr_1",
        approver="u_owner",
        comment="insufficient evidence",
    )
    assert event.name == "mission.rejected"
    payload = event.to_dict()
    assert payload["approval_id"] == "apr_1"
    assert payload["approver"] == "u_owner"
    assert payload["comment"] == "insufficient evidence"
