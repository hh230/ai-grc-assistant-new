"""Application service for the Plugin Management capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import PluginDTO
from .handlers import (
    DisablePluginHandler,
    EnablePluginHandler,
    GetPluginHandler,
    InstallPluginHandler,
    ListPluginsHandler,
)


class PluginApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def install(self, command: c.InstallPlugin, ctx: ExecutionContext) -> PluginDTO:
        return await InstallPluginHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def enable(self, command: c.EnablePlugin, ctx: ExecutionContext) -> PluginDTO:
        return await EnablePluginHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def disable(self, command: c.DisablePlugin, ctx: ExecutionContext) -> PluginDTO:
        return await DisablePluginHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def get(self, query: q.GetPlugin, ctx: ExecutionContext) -> PluginDTO:
        return await GetPluginHandler(self._uow, self._authz).handle(query, ctx)

    async def list(self, query: q.ListPlugins, ctx: ExecutionContext) -> list[PluginDTO]:
        return await ListPluginsHandler(self._uow, self._authz).handle(query, ctx)
