"""Workspaces router — the object-centric GRC work environment (CLAUDE.md §18)."""

from __future__ import annotations

from fastapi import APIRouter, status
from grc_domain.shared.identifiers import UserId, WorkspaceId
from grc_services.workspaces import commands as c
from grc_services.workspaces import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceResponse(ApiModel):
    id: str
    organization_id: str
    name: str
    owner_id: str
    status: str
    description: str | None
    member_ids: list[str]


class CreateWorkspaceRequest(ApiModel):
    name: str = Field(min_length=1)
    description: str | None = None
    owner_id: str | None = None


class WorkspaceMemberRequest(ApiModel):
    user_id: str = Field(min_length=1)


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
    responses=problem_responses(403, 422),
)
async def create_workspace(
    body: CreateWorkspaceRequest, commands: Commands, context: Context
) -> object:
    command = c.CreateWorkspace(
        name=body.name,
        description=body.description,
        owner_id=UserId(body.owner_id) if body.owner_id else None,
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[WorkspaceResponse],
    summary="List workspaces in the tenant",
    responses=problem_responses(403),
)
async def list_workspaces(queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.ListWorkspaces(), context))


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get a workspace",
    responses=problem_responses(403, 404),
)
async def get_workspace(workspace_id: str, queries: Queries, context: Context) -> object:
    return unwrap(
        await queries.ask(q.GetWorkspace(workspace_id=WorkspaceId(workspace_id)), context)
    )


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceResponse,
    summary="Add a workspace member",
    responses=problem_responses(403, 404, 422),
)
async def add_member(
    workspace_id: str, body: WorkspaceMemberRequest, commands: Commands, context: Context
) -> object:
    command = c.AddWorkspaceMember(
        workspace_id=WorkspaceId(workspace_id), user_id=UserId(body.user_id)
    )
    return unwrap(await commands.dispatch(command, context))


@router.delete(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceResponse,
    summary="Remove a workspace member",
    responses=problem_responses(403, 404),
)
async def remove_member(
    workspace_id: str, user_id: str, commands: Commands, context: Context
) -> object:
    command = c.RemoveWorkspaceMember(
        workspace_id=WorkspaceId(workspace_id), user_id=UserId(user_id)
    )
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{workspace_id}/archive",
    response_model=WorkspaceResponse,
    summary="Archive a workspace",
    responses=problem_responses(403, 404, 409),
)
async def archive_workspace(workspace_id: str, commands: Commands, context: Context) -> object:
    command = c.ArchiveWorkspace(workspace_id=WorkspaceId(workspace_id))
    return unwrap(await commands.dispatch(command, context))
