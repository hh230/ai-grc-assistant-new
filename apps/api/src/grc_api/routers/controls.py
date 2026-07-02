"""Controls router — customer control implementations and framework mappings (CLAUDE.md §13)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from grc_domain.controls.enums import ControlImplementationStatus
from grc_domain.shared.identifiers import (
    ControlId,
    EvidenceId,
    FrameworkControlId,
    FrameworkId,
    WorkspaceId,
)
from grc_services.controls import commands as c
from grc_services.controls import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/controls", tags=["controls"])


class ControlResponse(ApiModel):
    id: str
    organization_id: str
    workspace_id: str
    title: str
    implementation_status: str
    has_evidence: bool
    framework_control_count: int


class CreateControlRequest(ApiModel):
    workspace_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None


class MapControlRequest(ApiModel):
    framework_id: str = Field(min_length=1)
    framework_control_id: str = Field(min_length=1)


class LinkEvidenceRequest(ApiModel):
    evidence_id: str = Field(min_length=1)


class ImplementationStatusRequest(ApiModel):
    status: ControlImplementationStatus


@router.post(
    "",
    response_model=ControlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a control",
    responses=problem_responses(403, 422),
)
async def create_control(
    body: CreateControlRequest, commands: Commands, context: Context
) -> object:
    command = c.CreateControl(
        workspace_id=WorkspaceId(body.workspace_id), title=body.title, description=body.description
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[ControlResponse],
    summary="List controls in a workspace",
    responses=problem_responses(403),
)
async def list_controls(
    queries: Queries, context: Context, workspace_id: str = Query(...)
) -> object:
    query = q.ListControlsForWorkspace(workspace_id=WorkspaceId(workspace_id))
    return unwrap(await queries.ask(query, context))


@router.get(
    "/{control_id}",
    response_model=ControlResponse,
    summary="Get a control",
    responses=problem_responses(403, 404),
)
async def get_control(control_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.GetControl(control_id=ControlId(control_id)), context))


@router.post(
    "/{control_id}/framework-mappings",
    response_model=ControlResponse,
    summary="Map a control to a framework requirement",
    responses=problem_responses(403, 404, 422),
)
async def map_to_framework(
    control_id: str, body: MapControlRequest, commands: Commands, context: Context
) -> object:
    command = c.MapControlToFramework(
        control_id=ControlId(control_id),
        framework_id=FrameworkId(body.framework_id),
        framework_control_id=FrameworkControlId(body.framework_control_id),
    )
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{control_id}/evidence-links",
    response_model=ControlResponse,
    summary="Link evidence to a control",
    responses=problem_responses(403, 404, 422),
)
async def link_evidence(
    control_id: str, body: LinkEvidenceRequest, commands: Commands, context: Context
) -> object:
    command = c.LinkControlEvidence(
        control_id=ControlId(control_id), evidence_id=EvidenceId(body.evidence_id)
    )
    return unwrap(await commands.dispatch(command, context))


@router.put(
    "/{control_id}/implementation-status",
    response_model=ControlResponse,
    summary="Set a control's implementation status",
    responses=problem_responses(403, 404, 422),
)
async def set_implementation_status(
    control_id: str, body: ImplementationStatusRequest, commands: Commands, context: Context
) -> object:
    command = c.SetControlImplementationStatus(control_id=ControlId(control_id), status=body.status)
    return unwrap(await commands.dispatch(command, context))
