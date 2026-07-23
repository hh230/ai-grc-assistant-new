"""Pure, driver-free translation between the `Mission` aggregate and a plain storage row
(ADR 0043 §5–§6). Imports no database driver and does no I/O, so the whole round-trip is
unit-testable without Postgres. `PostgresMissionStore` (store.py) is the only module that knows
psycopg; it delegates all shape translation here.

Write side (`mission_to_row`) reuses each contract model's canonical `to_dict` — the platform's
one serialization convention (`pipeline_contracts.dataclass_dict`). Read side (`mission_from_row`)
reconstructs the aggregate **directly** via its constructor, including the full plan-version
history (`_plan_versions`, ADR 0042 §12.6) that `Mission.to_dict()` omits. Restoring a persisted
aggregate is not a lifecycle mutation: no transition guard is invoked or bypassed.

Every row carries a `payload_schema_version` (ADR 0043 §6, approved). This is the seam a shape
change rides on: **ADR 0044 Slice 1 bumps it 1 → 2** to add the mission's optional
`ApprovalRequest`. The codec reads **both** versions — a version-1 row simply has no approval
(`approval = None`), a version-2 row carries it — so old rows keep loading with no backfill. An
*unknown* version still fails loud rather than guessing.
"""

from __future__ import annotations

from typing import Any

from mission_engine import (
    ApprovalDecision,
    ApprovalRequest,
    Mission,
    MissionStatus,
    Plan,
    PlanStep,
    StepResult,
)
from pipeline_contracts import TenantContext

from mission_store.errors import UnsupportedPayloadSchemaVersion

# The serialization version the codec WRITES. Bumped only when a persisted shape (Plan / PlanStep /
# StepResult / TenantContext / ApprovalRequest) changes; a forward-compatible read path ships with
# each bump. ADR 0044 Slice 1 moved this 1 → 2 to persist the optional `ApprovalRequest`.
CURRENT_PAYLOAD_VERSION = 2

# The versions the codec can READ. Version 1 predates approval (its rows have no `approval`);
# version 2 carries the optional `ApprovalRequest`. A row outside this set fails loud (no guessing).
SUPPORTED_PAYLOAD_VERSIONS: frozenset[int] = frozenset({1, 2})

# The columns the codec owns, in a stable order. Store-managed columns (`revision`, `stored_at`,
# `row_updated_at`) are deliberately absent — they are the store's/DB's, never the aggregate's.
COLUMNS: tuple[str, ...] = (
    "id",
    "tenant_id",
    "principal_id",
    "region",
    "roles",
    "goal",
    "trace_id",
    "status",
    "execution_profile",
    "plan_version",
    "idempotency_key",
    "plan",
    "plan_versions",
    "step_results",
    "approval",
    "payload_schema_version",
    "created_at",
    "updated_at",
)

# Columns stored as JSONB. store.py wraps these (non-None) values for the driver; on read psycopg
# returns them already parsed, so `mission_from_row` consumes plain Python. `approval` is NULL when
# the mission has no active gate (ADR 0044, Slice 1).
JSONB_COLUMNS: frozenset[str] = frozenset(
    {"roles", "plan", "plan_versions", "step_results", "approval"}
)


# --- write side: aggregate → row --------------------------------------------------------


def mission_to_row(mission: Mission) -> dict[str, Any]:
    """The mission as a plain storage row (ADR 0042 §8; ADR 0043 §5–§6). Values are JSON-plain;
    the store wraps the JSONB columns for the driver."""
    tenant = mission.tenant
    profile = mission.execution_profile
    return {
        "id": mission.id,
        "tenant_id": tenant.tenant_id,
        "principal_id": tenant.principal_id,
        "region": tenant.region,
        "roles": list(tenant.roles),
        "goal": mission.goal,
        "trace_id": mission.trace_id,
        "status": mission.status.value,
        "execution_profile": profile.value if profile is not None else None,
        "plan_version": mission.plan_version,
        "idempotency_key": mission.idempotency_key,
        "plan": mission.plan.to_dict() if mission.plan is not None else None,
        "plan_versions": [plan.to_dict() for plan in mission.plan_versions],
        "step_results": [result.to_dict() for result in mission.step_results],
        "approval": mission.approval.to_dict() if mission.approval is not None else None,
        "payload_schema_version": CURRENT_PAYLOAD_VERSION,
        "created_at": mission.created_at,
        "updated_at": mission.updated_at,
    }


# --- read side: row → aggregate ---------------------------------------------------------


def _tenant_from_row(row: dict[str, Any]) -> TenantContext:
    return TenantContext(
        tenant_id=row["tenant_id"],
        principal_id=row.get("principal_id") or "",
        roles=tuple(row.get("roles") or ()),
        region=row.get("region") or "",
    )


def _plan_step_from_dict(data: dict[str, Any]) -> PlanStep:
    return PlanStep(
        description=data.get("description", ""),
        instruction=data.get("instruction", ""),
        consequential=bool(data.get("consequential", False)),
        # ADR 0048: old plans (written before the field existed) read back as tool="", i.e. the
        # executor's default tool — so no payload_schema_version bump is needed for this scalar.
        tool=data.get("tool", ""),
        id=data["id"],
    )


def _plan_from_dict(data: dict[str, Any]) -> Plan:
    # `data` carries a computed `execution_profile` key (Plan.to_dict adds it); it is derived from
    # the steps, so we ignore it on the way in and let the aggregate recompute.
    return Plan(
        steps=tuple(_plan_step_from_dict(step) for step in data["steps"]),
        version=int(data.get("version", 1)),
    )


def _approval_decision_from_dict(data: dict[str, Any]) -> ApprovalDecision:
    return ApprovalDecision(
        approved=bool(data["approved"]),
        approver=data.get("approver", ""),
        comment=data.get("comment", ""),
        decided_at=float(data.get("decided_at", 0.0)),
    )


def _approval_from_dict(data: dict[str, Any]) -> ApprovalRequest:
    """Rebuild the mission's `ApprovalRequest` (ADR 0044, Slice 1), including its optional nested
    `ApprovalDecision`. Present only in version-2 rows; a version-1 row has no approval at all."""
    decision = data.get("decision")
    return ApprovalRequest(
        reason=data.get("reason", ""),
        requested_by=data.get("requested_by", ""),
        requested_at=float(data.get("requested_at", 0.0)),
        id=data["id"],
        decision=_approval_decision_from_dict(decision) if decision else None,
    )


def _step_result_from_dict(data: dict[str, Any]) -> StepResult:
    return StepResult(
        step_id=data["step_id"],
        ok=bool(data.get("ok", True)),
        output=data.get("output", ""),
        citations=tuple(data.get("citations") or ()),
        confidence=data.get("confidence"),
        source_ids=tuple(data.get("source_ids") or ()),
        latency_ms=float(data.get("latency_ms", 0.0)),
        estimated_cost=data.get("estimated_cost"),
        warnings=tuple(data.get("warnings") or ()),
    )


def mission_from_row(row: dict[str, Any]) -> Mission:
    """Reconstruct the aggregate from a storage row, restoring its exact status and full
    plan-version history. Constructed directly (not replayed through transitions): a persisted
    mission is restored, not re-driven."""
    version = int(row.get("payload_schema_version", CURRENT_PAYLOAD_VERSION))
    if version not in SUPPORTED_PAYLOAD_VERSIONS:
        raise UnsupportedPayloadSchemaVersion(
            mission_id=row["id"], found=version, supported=CURRENT_PAYLOAD_VERSION
        )
    plan_data = row.get("plan")
    # `approval` is absent/NULL in version-1 rows (predating ADR 0044) → None; a version-2 row
    # carries the mission's optional ApprovalRequest. Reading `.get` covers both uniformly.
    approval_data = row.get("approval")
    return Mission(
        id=row["id"],
        tenant=_tenant_from_row(row),
        goal=row["goal"],
        trace_id=row["trace_id"],
        status=MissionStatus(row["status"]),
        plan=_plan_from_dict(plan_data) if plan_data else None,
        step_results=[_step_result_from_dict(item) for item in (row.get("step_results") or [])],
        idempotency_key=row.get("idempotency_key") or "",
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        approval=_approval_from_dict(approval_data) if approval_data else None,
        _plan_versions=[_plan_from_dict(item) for item in (row.get("plan_versions") or [])],
    )
