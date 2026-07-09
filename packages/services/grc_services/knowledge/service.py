"""Application service for the Knowledge capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import KnowledgeSourceDTO
from .handlers import (
    GetKnowledgeSourceHandler,
    ListKnowledgeSourcesHandler,
    RegisterKnowledgeSourceHandler,
)


class KnowledgeApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def register(
        self, command: c.RegisterKnowledgeSource, ctx: ExecutionContext
    ) -> KnowledgeSourceDTO:
        handler = RegisterKnowledgeSourceHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def get(self, query: q.GetKnowledgeSource, ctx: ExecutionContext) -> KnowledgeSourceDTO:
        return await GetKnowledgeSourceHandler(self._uow, self._authz).handle(query, ctx)

    async def list(
        self, query: q.ListKnowledgeSources, ctx: ExecutionContext
    ) -> list[KnowledgeSourceDTO]:
        return await ListKnowledgeSourcesHandler(self._uow, self._authz).handle(query, ctx)
