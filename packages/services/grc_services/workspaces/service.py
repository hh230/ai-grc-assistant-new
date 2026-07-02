"""Application service for the Workspace capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import WorkspaceDTO
from .handlers import (
    AddWorkspaceMemberHandler,
    ArchiveWorkspaceHandler,
    CreateWorkspaceHandler,
    GetWorkspaceHandler,
    ListWorkspacesHandler,
    RemoveWorkspaceMemberHandler,
)


class WorkspaceApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def create(self, command: c.CreateWorkspace, ctx: ExecutionContext) -> WorkspaceDTO:
        return await CreateWorkspaceHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def add_member(
        self, command: c.AddWorkspaceMember, ctx: ExecutionContext
    ) -> WorkspaceDTO:
        return await AddWorkspaceMemberHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def remove_member(
        self, command: c.RemoveWorkspaceMember, ctx: ExecutionContext
    ) -> WorkspaceDTO:
        return await RemoveWorkspaceMemberHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def archive(self, command: c.ArchiveWorkspace, ctx: ExecutionContext) -> WorkspaceDTO:
        return await ArchiveWorkspaceHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def get(self, query: q.GetWorkspace, ctx: ExecutionContext) -> WorkspaceDTO:
        return await GetWorkspaceHandler(self._uow, self._authz).handle(query, ctx)

    async def list(self, query: q.ListWorkspaces, ctx: ExecutionContext) -> list[WorkspaceDTO]:
        return await ListWorkspacesHandler(self._uow, self._authz).handle(query, ctx)
