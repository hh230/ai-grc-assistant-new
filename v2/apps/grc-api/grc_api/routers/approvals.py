"""`GET /v1/approvals?status=waiting` — the Decisions queue (REST_API_CONTRACT_V1 §4; Slice S6).

Thin: resolve the tenant (fail-closed), read the `ApprovalQueueProjection` (composed in `deps` from
the store + the reused mission-read-model), shape the response. No business logic here; the
projection is read-only and computed-on-read. Approve/Reject are the **reused S2** commands (see
`missions.py`) — this router only serves the read. Product word "Decisions"; path stays
`/v1/approvals`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from mission_application import ApprovalQueueProjection
from pipeline_contracts import TenantContext

from grc_api.deps import get_approval_queue
from grc_api.schemas import DecisionsResponse, RecentDecisionsResponse
from grc_api.security import require_tenant

router = APIRouter()


@router.get("/approvals", response_model=None)
def list_approvals(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    projection: Annotated[ApprovalQueueProjection, Depends(get_approval_queue)],
    status: Annotated[str, Query()] = "waiting",
) -> DecisionsResponse | RecentDecisionsResponse:
    # `status=waiting` (default) is the queue — the page's reason to exist. `status=decided` is the
    # recent decisions shown when nothing is waiting — a read-only history, no new command. Approver
    # role guard declared (enforcement deferred, like the other guards).
    if status == "decided":
        return RecentDecisionsResponse.from_items(projection.recent_decisions(tenant))
    return DecisionsResponse.from_items(projection.execute(tenant))
