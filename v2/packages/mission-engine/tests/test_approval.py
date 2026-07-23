"""Slice 1 of the Human Approval lifecycle (ADR 0044): the Mission aggregate can *carry* a pending
`ApprovalRequest` and honour the one-active-request invariant. There is **no** approve/reject here —
`ApprovalDecision` is only ever `None` in Slice 1 — and no events; those are Slice 2.
"""

from __future__ import annotations

import pytest
from mission_engine import (
    ApprovalDecision,
    ApprovalError,
    ApprovalRequest,
    Mission,
    MissionStatus,
    Plan,
    PlanStep,
)
from pipeline_contracts import TenantContext


def _executing_mission(tenant: TenantContext) -> Mission:
    """A mission driven to EXECUTING (the state the engine pauses from at a consequential step)."""
    mission = Mission.create(goal="draft an access-control policy", tenant=tenant)
    mission.set_plan(
        Plan(steps=(PlanStep(description="author", instruction="write", consequential=True),))
    )
    mission.begin_execution()
    return mission


# ── value objects ─────────────────────────────────────────────────────────────
def test_approval_request_defaults_to_pending() -> None:
    request = ApprovalRequest(reason="writes a policy", requested_by="mission", requested_at=1.0)
    assert request.decision is None
    assert request.is_pending
    assert request.id.startswith("apr_")  # minted, self-describing id


def test_distinct_requests_get_distinct_ids() -> None:
    assert ApprovalRequest().id != ApprovalRequest().id


def test_approval_request_to_dict_round_trips_shape() -> None:
    request = ApprovalRequest(reason="r", requested_by="mission", requested_at=2.5, id="apr_fixed")
    assert request.to_dict() == {
        "reason": "r",
        "requested_by": "mission",
        "requested_at": 2.5,
        "id": "apr_fixed",
        "decision": None,  # pending: no decision serialized (Slice 1 never sets one)
    }


def test_approval_decision_value_object_serializes_flat() -> None:
    # The ApprovalDecision type exists in Slice 1 (defined now, populated in Slice 2); its shape is
    # locked here even though the aggregate never attaches one yet.
    decision = ApprovalDecision(approved=True, approver="u_owner", comment="ok", decided_at=9.0)
    assert decision.to_dict() == {
        "approved": True,
        "approver": "u_owner",
        "comment": "ok",
        "decided_at": 9.0,
    }
    # nested inside a request, to_dict serializes it automatically
    nested = ApprovalRequest(id="apr_x", decision=decision)
    assert nested.to_dict()["decision"] == decision.to_dict()


# ── aggregate carries the request ─────────────────────────────────────────────
def test_await_approval_without_a_request_keeps_frozen_behaviour(tenant: TenantContext) -> None:
    mission = _executing_mission(tenant)
    mission.await_approval()  # the frozen no-arg call
    assert mission.status is MissionStatus.AWAITING_APPROVAL
    assert mission.approval is None
    assert not mission.has_active_approval


def test_await_approval_attaches_the_request(tenant: TenantContext) -> None:
    mission = _executing_mission(tenant)
    request = ApprovalRequest(reason="writes a policy", requested_by="mission", requested_at=1.0)
    mission.await_approval(request)
    assert mission.status is MissionStatus.AWAITING_APPROVAL
    assert mission.approval is request
    assert mission.has_active_approval  # pending → active


def test_mission_to_dict_includes_the_approval(tenant: TenantContext) -> None:
    mission = _executing_mission(tenant)
    request = ApprovalRequest(reason="r", requested_by="mission", requested_at=1.0, id="apr_1")
    mission.await_approval(request)
    assert mission.to_dict()["approval"] == request.to_dict()


def test_a_mission_without_a_gate_has_no_active_approval(tenant: TenantContext) -> None:
    mission = Mission.create(goal="g", tenant=tenant)
    assert mission.approval is None
    assert not mission.has_active_approval


# ── the one-active-request invariant (ADR 0044) ───────────────────────────────
def test_cannot_attach_a_second_active_request(tenant: TenantContext) -> None:
    """At most one active (pending) ApprovalRequest per mission. Constructed white-box in EXECUTING
    while already holding a pending request, a further attach is rejected — never silently
    overwriting the open gate."""
    existing = ApprovalRequest(reason="first", requested_by="mission", requested_at=1.0)
    mission = Mission(
        id="mis_x",
        tenant=tenant,
        goal="g",
        trace_id="trc_x",
        status=MissionStatus.EXECUTING,
        approval=existing,
        created_at=1.0,
        updated_at=1.0,
    )
    assert mission.has_active_approval
    with pytest.raises(ApprovalError, match="one is allowed"):
        mission.await_approval(ApprovalRequest(reason="second", requested_by="mission"))
    assert mission.approval is existing  # the open gate is untouched
