"""Application service for the Tool Management capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import ToolDTO
from .handlers import (
    DeprecateToolHandler,
    GetToolHandler,
    ListActiveToolsHandler,
    RegisterToolHandler,
)


class ToolApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def register(self, command: c.RegisterTool, ctx: ExecutionContext) -> ToolDTO:
        return await RegisterToolHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def deprecate(self, command: c.DeprecateTool, ctx: ExecutionContext) -> ToolDTO:
        return await DeprecateToolHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def get(self, query: q.GetTool, ctx: ExecutionContext) -> ToolDTO:
        return await GetToolHandler(self._uow, self._authz).handle(query, ctx)

    async def list_active(self, query: q.ListActiveTools, ctx: ExecutionContext) -> list[ToolDTO]:
        return await ListActiveToolsHandler(self._uow, self._authz).handle(query, ctx)
