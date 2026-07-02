"""Application service for the Framework capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import FrameworkDTO
from .handlers import (
    DeprecateFrameworkHandler,
    GetFrameworkHandler,
    ImportFrameworkHandler,
    ListPublishedFrameworksHandler,
    PublishFrameworkHandler,
)


class FrameworkApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def import_definition(
        self, command: c.ImportFramework, ctx: ExecutionContext
    ) -> FrameworkDTO:
        return await ImportFrameworkHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def publish(self, command: c.PublishFramework, ctx: ExecutionContext) -> FrameworkDTO:
        return await PublishFrameworkHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def deprecate(self, command: c.DeprecateFramework, ctx: ExecutionContext) -> FrameworkDTO:
        return await DeprecateFrameworkHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def get(self, query: q.GetFramework, ctx: ExecutionContext) -> FrameworkDTO:
        return await GetFrameworkHandler(self._uow, self._authz).handle(query, ctx)

    async def list_published(
        self, query: q.ListPublishedFrameworks, ctx: ExecutionContext
    ) -> list[FrameworkDTO]:
        return await ListPublishedFrameworksHandler(self._uow, self._authz).handle(query, ctx)
