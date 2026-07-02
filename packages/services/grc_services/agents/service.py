"""Application service for the Agent Management capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import AgentDTO
from .handlers import GetAgentHandler, ListActiveAgentsHandler, RegisterAgentHandler


class AgentApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def register(self, command: c.RegisterAgent, ctx: ExecutionContext) -> AgentDTO:
        return await RegisterAgentHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def get(self, query: q.GetAgent, ctx: ExecutionContext) -> AgentDTO:
        return await GetAgentHandler(self._uow, self._authz).handle(query, ctx)

    async def list_active(self, query: q.ListActiveAgents, ctx: ExecutionContext) -> list[AgentDTO]:
        return await ListActiveAgentsHandler(self._uow, self._authz).handle(query, ctx)
