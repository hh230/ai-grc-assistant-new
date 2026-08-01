"""`GET /v1/dashboard` — the Dashboard Projection (REST_API_CONTRACT_V1 §4; Slice S5).

The route is thin and **reads one projection** — it holds no business logic (design rule 1). The
`DashboardProjection` (composed in `deps`) does the computed-on-read aggregation over the reused
`mission-read-model` + `ResultQuery`; the route only resolves the tenant (fail-closed) and shapes
the response. "What needs my attention right now?" — attention counts first, Coverage Snapshot last.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from mission_application import DashboardProjection
from pipeline_contracts import TenantContext

from grc_api.deps import get_dashboard_projection
from grc_api.schemas import DashboardResponse
from grc_api.security import require_tenant

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    projection: Annotated[DashboardProjection, Depends(get_dashboard_projection)],
) -> DashboardResponse:
    return DashboardResponse.from_view(projection.execute(tenant))
