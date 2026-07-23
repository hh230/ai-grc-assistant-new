"""`GET /v1/missions` — the Mission List query (REST_API_CONTRACT_V1 §4; Execution Slice S1).

The route is thin: resolve the tenant (fail-closed), read the tenant-scoped read model, shape the
page. All logic — filtering, search, paging, isolation — lives in `mission-read-model`. The route
invents nothing; `status`, `type`, `q`, `page`, `page_size` map straight to the read-model call.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from mission_application import (
    ApproveInputs,
    ApproveMissionStepCommand,
    CommandContext,
    CommandResult,
    CreateMissionCommand,
    CreateMissionInputs,
    ExportService,
    MissionDetailQuery,
    MissionDetailView,
    RejectInputs,
    RejectMissionStepCommand,
    ResultQuery,
    ResultView,
    StartInputs,
    StartMissionCommand,
)
from mission_read_model import DEFAULT_PAGE_SIZE, MissionListReadModel
from pipeline_contracts import TenantContext

from grc_api.deps import (
    get_approve_command,
    get_create_command,
    get_export_service,
    get_mission_catalog,
    get_mission_detail_query,
    get_mission_read_model,
    get_reject_command,
    get_result_query,
    get_start_command,
    require_context,
)
from grc_api.errors import ApiError
from grc_api.schemas import (
    CreateMissionBody,
    DecisionBody,
    MissionCreatedResponse,
    MissionListResponse,
)
from grc_api.security import require_tenant

router = APIRouter()


@router.get("/missions", response_model=MissionListResponse)
def list_missions(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    read_model: Annotated[MissionListReadModel, Depends(get_mission_read_model)],
    status: Annotated[str | None, Query()] = None,
    mission_type: Annotated[str | None, Query(alias="type")] = None,
    q: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = DEFAULT_PAGE_SIZE,
) -> MissionListResponse:
    page_obj = read_model.list_missions(
        tenant,
        status=status,
        mission_type=mission_type,
        query=q,
        page=page,
        page_size=page_size,
    )
    return MissionListResponse.from_page(page_obj)


@router.post("/missions", response_model=MissionCreatedResponse, status_code=201)
def create_mission(
    body: CreateMissionBody,
    context: Annotated[CommandContext, Depends(require_context)],
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    command: Annotated[CreateMissionCommand, Depends(get_create_command)],
    query: Annotated[MissionDetailQuery, Depends(get_mission_detail_query)],
    catalog: Annotated[Any, Depends(get_mission_catalog)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> MissionCreatedResponse:
    # Validate the product vocabulary at the boundary: the type must be one of the 6 registered.
    if body.type not in catalog:
        raise ApiError(
            status_code=400, code="validation_error", message=f"unknown mission type: {body.type!r}"
        )
    result = command.execute(
        context,
        CreateMissionInputs(
            mission_type=body.type,
            scope=body.scope,
            document_ids=tuple(body.document_ids),
            idempotency_key=idempotency_key,
        ),
    )
    # The review station: the mission's detail (type · scope · status · plan) plus the plan summary
    # (steps · human approvals). Reuses the S2 detail query; the mission was just projected.
    view = query.execute(result.mission_id, tenant)
    if view is None:  # pragma: no cover - just created + projected, so present
        raise ApiError(status_code=404, code="not_found", message="mission not found")
    return MissionCreatedResponse(
        mission=view, steps=result.steps, human_approvals=result.human_approvals
    )


@router.post("/missions/{mission_id}/run", response_model=CommandResult)
def start_mission(
    mission_id: str,
    context: Annotated[CommandContext, Depends(require_context)],
    command: Annotated[StartMissionCommand, Depends(get_start_command)],
) -> CommandResult:
    # The product's "Start mission" (the /run path is the frozen-contract detail). The command
    # reuses the MissionCommand template; IllegalCommand (already started) → 409 via the handler.
    return command.execute(context, mission_id, StartInputs())


@router.get("/missions/{mission_id}", response_model=MissionDetailView)
def get_mission(
    mission_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    query: Annotated[MissionDetailQuery, Depends(get_mission_detail_query)],
) -> MissionDetailView:
    # Thin adapter: the Application Query composes the sources and maps the View Model; the route
    # only resolves the tenant and turns "not found" (fail-closed) into a 404.
    view = query.execute(mission_id, tenant)
    if view is None:
        raise ApiError(status_code=404, code="not_found", message="mission not found")
    return view


@router.post(
    "/missions/{mission_id}/approvals/{step_id}/approve", response_model=CommandResult
)
def approve_step(
    mission_id: str,
    step_id: str,
    context: Annotated[CommandContext, Depends(require_context)],
    command: Annotated[ApproveMissionStepCommand, Depends(get_approve_command)],
    body: DecisionBody | None = None,
) -> CommandResult:
    # Thin adapter: the command holds the policy (Approver role, state precondition) and drives the
    # Core; a typed Application error propagates to the handler → 403/404/409 (ADR 0054).
    comment = body.comment if body is not None else ""
    return command.execute(context, mission_id, ApproveInputs(step_id=step_id, comment=comment))


@router.post(
    "/missions/{mission_id}/approvals/{step_id}/reject", response_model=CommandResult
)
def reject_step(
    mission_id: str,
    step_id: str,
    context: Annotated[CommandContext, Depends(require_context)],
    command: Annotated[RejectMissionStepCommand, Depends(get_reject_command)],
    body: DecisionBody | None = None,
) -> CommandResult:
    comment = body.comment if body is not None else ""
    return command.execute(context, mission_id, RejectInputs(step_id=step_id, comment=comment))


@router.get("/missions/{mission_id}/deliverable", response_model=None)
def get_deliverable(
    mission_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    query: Annotated[ResultQuery, Depends(get_result_query)],
) -> ResultView:
    # The query enforces the rules: None → 404 (absent/cross-tenant), DeliverableNotReady → 409
    # (not completed; mapped by the handler). The result is a View Model — "Result" to the user.
    result = query.execute(mission_id, tenant)
    if result is None:
        raise ApiError(status_code=404, code="not_found", message="mission not found")
    return result


@router.get("/missions/{mission_id}/deliverable/export")
def export_deliverable(
    mission_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    query: Annotated[ResultQuery, Depends(get_result_query)],
    export_service: Annotated[ExportService, Depends(get_export_service)],
    fmt: Annotated[str, Query(alias="format")],
) -> Response:
    # Export the Result the user sees (not the mission). Unknown format → UnsupportedFormat → 400.
    result = query.execute(mission_id, tenant)
    if result is None:
        raise ApiError(status_code=404, code="not_found", message="mission not found")
    exported = export_service.export(result, fmt)
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )
