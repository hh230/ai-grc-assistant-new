"""Slice 1 of Human Approval (ADR 0044) at the persistence seam: the codec round-trips the mission's
optional `ApprovalRequest` under `payload_schema_version = 2`, and still reads legacy version-1 rows
(which predate approval) as `approval = None`. Pure — no database needed.
"""

from __future__ import annotations

from typing import Any

from mission_engine import ApprovalRequest, Mission, MissionStatus, Plan, PlanStep
from mission_store.codec import (
    COLUMNS,
    CURRENT_PAYLOAD_VERSION,
    SUPPORTED_PAYLOAD_VERSIONS,
    mission_from_row,
    mission_to_row,
)
from pipeline_contracts import TenantContext

_TENANT = TenantContext(tenant_id="org_acme", principal_id="u_owner", roles=("owner",))


def _paused_mission_with_approval() -> tuple[Mission, ApprovalRequest]:
    mission = Mission.create(goal="draft an access-control policy", tenant=_TENANT)
    mission.set_plan(
        Plan(steps=(PlanStep(description="author", instruction="write", consequential=True),))
    )
    mission.begin_execution()
    request = ApprovalRequest(
        reason="writes an access-control policy", requested_by="mission", requested_at=12.5
    )
    mission.await_approval(request)
    return mission, request


# ── version + column wiring ───────────────────────────────────────────────────
def test_current_write_version_is_2() -> None:
    assert CURRENT_PAYLOAD_VERSION == 2
    assert frozenset({1, 2}) == SUPPORTED_PAYLOAD_VERSIONS


def test_row_carries_the_approval_column() -> None:
    assert "approval" in COLUMNS
    mission, _ = _paused_mission_with_approval()
    row = mission_to_row(mission)
    assert tuple(row.keys()) == COLUMNS
    assert row["payload_schema_version"] == 2
    assert row["approval"] is not None


# ── round-trip: a mission carrying a pending approval ─────────────────────────
def test_pending_approval_round_trips_without_loss() -> None:
    mission, request = _paused_mission_with_approval()
    restored = mission_from_row(mission_to_row(mission))

    assert restored.status is MissionStatus.AWAITING_APPROVAL
    assert restored.approval is not None
    assert restored.approval == request  # value-object equality: every field survived
    assert restored.approval.id == request.id
    assert restored.approval.is_pending
    assert restored.has_active_approval
    assert restored.to_dict() == mission.to_dict()


# ── a mission with no gate: approval is None on both sides ─────────────────────
def test_mission_without_approval_round_trips_as_none() -> None:
    mission = Mission.create(goal="g", tenant=_TENANT)
    row = mission_to_row(mission)
    assert row["approval"] is None
    restored = mission_from_row(row)
    assert restored.approval is None
    assert not restored.has_active_approval


# ── backward compatibility: a legacy version-1 row (predates approval) ─────────
def test_version_1_row_without_approval_reads_as_none() -> None:
    """A row written before ADR 0044 has payload_schema_version = 1 and no `approval` key at all.
    The codec must read it — approval is simply absent → None — never fail."""
    mission = Mission.create(goal="legacy", tenant=_TENANT)
    row: dict[str, Any] = mission_to_row(mission)
    # simulate an on-disk version-1 row: old version, and the column absent entirely
    row["payload_schema_version"] = 1
    row.pop("approval")

    restored = mission_from_row(row)
    assert restored.approval is None
    assert restored.goal == "legacy"


def test_version_1_row_with_null_approval_column_reads_as_none() -> None:
    """After migration 0003, a pre-existing row has payload_schema_version = 1 and a NULL `approval`
    column (present but empty). That must also read as no approval."""
    mission = Mission.create(goal="legacy", tenant=_TENANT)
    row = mission_to_row(mission)
    row["payload_schema_version"] = 1
    row["approval"] = None  # column exists (added by 0003) but NULL for old rows

    restored = mission_from_row(row)
    assert restored.approval is None
