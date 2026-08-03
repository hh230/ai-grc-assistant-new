"""`/v1/governance-plans/*` — the living Governance Plan (ADR 0066 §3.1, §5).

Creating and running the plan itself is **not** a new endpoint: `generate_governance_plan` is just
another Mission Catalog entry, so it goes through the existing generic `/v1/missions` create → run
→ approve flow (`routers/missions.py`) like every other mission type — including its one
consequential step (`finalize_plan`) pausing at the same ADR 0044 human-approval gate. What is
genuinely new here is what happens *after* a plan exists: reading the active version and its
items, listing the tenant's full version lineage (§3.1 — plans are immutable snapshots, never
edited in place), and the day-to-day execution actions (§5) — mark an item done, reopen it,
attach optional evidence, and read the live, reversible maturity recalculation. None of this is
Mission-governed (§5.1: execution can run for a year; a Mission cannot), so it is plain
tenant-scoped CRUD over `PlanExecutionService` and the store.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from governance_plan_execution import PlanExecutionService, PlanItemConflict, PlanItemNotFound
from pipeline_contracts import TenantContext

from grc_api.deps import get_governance_store, get_plan_execution_service
from grc_api.errors import ApiError
from grc_api.governance_plan_schemas import (
    AttachEvidenceBody,
    CurrentMaturityResponse,
    PlanDetailResponse,
    PlanEventsResponse,
    PlanItemView,
    PlanVersionsResponse,
)
from grc_api.security import require_tenant

router = APIRouter()


@router.get("/governance-plans/active", response_model=PlanDetailResponse | None)
def get_active_plan(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_governance_store)],
) -> PlanDetailResponse | None:
    plan = store.get_active_plan(tenant.tenant_id)
    if plan is None:
        return None
    items = store.list_plan_items(plan.id, tenant.tenant_id)
    return PlanDetailResponse.build(plan, items)


@router.get("/governance-plans/versions", response_model=PlanVersionsResponse)
def list_plan_versions(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_governance_store)],
) -> PlanVersionsResponse:
    """The tenant's full lineage, oldest first (§3.1) — how the user compares versions over time."""
    return PlanVersionsResponse.from_plans(store.list_plan_versions(tenant.tenant_id))


@router.get("/governance-plans/maturity", response_model=CurrentMaturityResponse)
def get_current_maturity(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    service: Annotated[PlanExecutionService, Depends(get_plan_execution_service)],
) -> CurrentMaturityResponse:
    """Reversible by construction (§5.3): the frozen Discovery baseline plus whichever items are
    CURRENTLY done — recomputed fresh on every call, never a stored value."""
    return CurrentMaturityResponse.from_current(service.current_maturity(tenant.tenant_id))


@router.get("/governance-plans/{plan_id}", response_model=PlanDetailResponse)
def get_plan(
    plan_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_governance_store)],
) -> PlanDetailResponse:
    plan = store.get_plan(plan_id, tenant.tenant_id)
    if plan is None:
        raise ApiError(status_code=404, code="not_found", message="governance plan not found")
    items = store.list_plan_items(plan.id, tenant.tenant_id)
    return PlanDetailResponse.build(plan, items)


@router.post("/governance-plans/items/{item_id}/start", response_model=PlanItemView)
def start_item(
    item_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    service: Annotated[PlanExecutionService, Depends(get_plan_execution_service)],
) -> PlanItemView:
    """Not started -> in progress (Phase 4). Idempotent from `not_started` only; a no-op on an
    already `in_progress`/`done` item, never a conflict."""
    try:
        item = service.start(item_id, tenant.tenant_id, tenant.principal_id)
    except PlanItemNotFound as exc:
        raise ApiError(status_code=404, code="not_found", message=str(exc)) from exc
    except PlanItemConflict as exc:
        raise ApiError(status_code=409, code="conflict", message=str(exc)) from exc
    return PlanItemView.from_item(item)


@router.post("/governance-plans/items/{item_id}/complete", response_model=PlanItemView)
def complete_item(
    item_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    service: Annotated[PlanExecutionService, Depends(get_plan_execution_service)],
) -> PlanItemView:
    """Evidence is never checked (§5.4) — completion is the practitioner's own attestation.
    Idempotent: completing an already-done item is a no-op, not an error. `409` means someone else
    changed the item first (Phase 3 hardening's optimistic lock) — re-fetch and retry."""
    try:
        item = service.mark_done(item_id, tenant.tenant_id, tenant.principal_id)
    except PlanItemNotFound as exc:
        raise ApiError(status_code=404, code="not_found", message=str(exc)) from exc
    except PlanItemConflict as exc:
        raise ApiError(status_code=409, code="conflict", message=str(exc)) from exc
    return PlanItemView.from_item(item)


@router.post("/governance-plans/items/{item_id}/reopen", response_model=PlanItemView)
def reopen_item(
    item_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    service: Annotated[PlanExecutionService, Depends(get_plan_execution_service)],
) -> PlanItemView:
    """Reversible by construction (§5.3): no undo logic beyond this call — the item simply stops
    counting toward the next `current_maturity()` recalculation."""
    try:
        item = service.reopen(item_id, tenant.tenant_id, tenant.principal_id)
    except PlanItemNotFound as exc:
        raise ApiError(status_code=404, code="not_found", message=str(exc)) from exc
    except PlanItemConflict as exc:
        raise ApiError(status_code=409, code="conflict", message=str(exc)) from exc
    return PlanItemView.from_item(item)


@router.get("/governance-plans/items/{item_id}/events", response_model=PlanEventsResponse)
def list_item_events(
    item_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_governance_store)],
) -> PlanEventsResponse:
    """The audit trail for one item, in the order it actually happened (Phase 3 hardening) — what
    a reviewer reaches for to confirm a completion has (or doesn't have) a matching event."""
    if store.get_plan_item(item_id, tenant.tenant_id) is None:
        raise ApiError(status_code=404, code="not_found", message="plan item not found")
    return PlanEventsResponse.from_events(store.list_plan_events(item_id, tenant.tenant_id))


@router.post("/governance-plans/items/{item_id}/evidence", response_model=PlanItemView)
def attach_evidence(
    item_id: str,
    body: AttachEvidenceBody,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    service: Annotated[PlanExecutionService, Depends(get_plan_execution_service)],
) -> PlanItemView:
    """Always additive and optional (§5.4) — never a gate on `complete`; callable before or
    after."""
    try:
        item = service.attach_evidence(
            item_id, tenant.tenant_id, tuple(body.evidence_ids), tenant.principal_id
        )
    except PlanItemNotFound as exc:
        raise ApiError(status_code=404, code="not_found", message=str(exc)) from exc
    except PlanItemConflict as exc:
        raise ApiError(status_code=409, code="conflict", message=str(exc)) from exc
    return PlanItemView.from_item(item)
