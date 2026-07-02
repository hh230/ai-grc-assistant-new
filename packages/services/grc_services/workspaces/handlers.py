"""Use cases for the Workspace capability."""

from __future__ import annotations

from grc_domain.shared.identifiers import WorkspaceId
from grc_domain.workspace.entities import Workspace

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import (
    AddWorkspaceMember,
    ArchiveWorkspace,
    CreateWorkspace,
    RemoveWorkspaceMember,
)
from .dtos import WorkspaceDTO
from .queries import GetWorkspace, ListWorkspaces


async def _load(uow: UnitOfWork, ctx: ExecutionContext, workspace_id: WorkspaceId) -> Workspace:
    ws = await uow.workspaces.get(ctx.organization_id, workspace_id)
    if ws is None:
        raise ResourceNotFoundError(f"Workspace {workspace_id} not found")
    return ws


class CreateWorkspaceHandler(TransactionalCommandHandler[CreateWorkspace, WorkspaceDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.WORKSPACE)
        ws = Workspace.create(
            id=WorkspaceId.generate(),
            organization_id=context.organization_id,
            name=command.name,
            owner_id=command.owner_id or context.user_id,
            description=command.description,
        )
        await uow.workspaces.add(ws)
        return WorkspaceDTO.from_domain(ws)


class AddWorkspaceMemberHandler(TransactionalCommandHandler[AddWorkspaceMember, WorkspaceDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.WORKSPACE, str(command.workspace_id)
        )
        ws = await _load(uow, context, command.workspace_id)
        ws.add_member(command.user_id)
        await uow.workspaces.save(ws)
        return WorkspaceDTO.from_domain(ws)


class RemoveWorkspaceMemberHandler(
    TransactionalCommandHandler[RemoveWorkspaceMember, WorkspaceDTO]
):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.WORKSPACE, str(command.workspace_id)
        )
        ws = await _load(uow, context, command.workspace_id)
        ws.remove_member(command.user_id)
        await uow.workspaces.save(ws)
        return WorkspaceDTO.from_domain(ws)


class ArchiveWorkspaceHandler(TransactionalCommandHandler[ArchiveWorkspace, WorkspaceDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.WORKSPACE, str(command.workspace_id)
        )
        ws = await _load(uow, context, command.workspace_id)
        ws.archive()
        await uow.workspaces.save(ws)
        return WorkspaceDTO.from_domain(ws)


class GetWorkspaceHandler(QueryHandler[GetWorkspace, WorkspaceDTO]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.WORKSPACE, str(query.workspace_id)
        )
        async with self._uow as uow:
            ws = await uow.workspaces.get(context.organization_id, query.workspace_id)
        if ws is None:
            raise ResourceNotFoundError(f"Workspace {query.workspace_id} not found")
        return WorkspaceDTO.from_domain(ws)


class ListWorkspacesHandler(QueryHandler[ListWorkspaces, list[WorkspaceDTO]]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.READ, ResourceType.WORKSPACE)
        async with self._uow as uow:
            items = await uow.workspaces.list_for_organization(context.organization_id)
        return [WorkspaceDTO.from_domain(w) for w in items]
