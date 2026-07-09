"""Use cases for the Agent Management capability."""

from __future__ import annotations

from grc_domain.platform.entities import AgentDescriptor
from grc_domain.shared.identifiers import AgentId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import RegisterAgent
from .dtos import AgentDTO
from .queries import GetAgent, ListActiveAgents


class RegisterAgentHandler(TransactionalCommandHandler[RegisterAgent, AgentDTO]):
    async def _execute(
        self, command: RegisterAgent, context: ExecutionContext, uow: UnitOfWork
    ) -> AgentDTO:
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.AGENT)
        agent = AgentDescriptor.register(
            id=AgentId.generate(),
            name=command.name,
            agent_type=command.agent_type,
            allowed_tool_ids=frozenset(command.allowed_tool_ids),
            data_scopes=frozenset(command.data_scopes),
        )
        await uow.agents.add(agent)
        return AgentDTO.from_domain(agent)


class GetAgentHandler(QueryHandler[GetAgent, AgentDTO]):
    async def handle(
        self, query: GetAgent, context: ExecutionContext
    ) -> AgentDTO:
        await self._authz.ensure_can(context, Action.READ, ResourceType.AGENT, str(query.agent_id))
        async with self._uow as uow:
            agent = await uow.agents.get(query.agent_id)
        if agent is None:
            raise ResourceNotFoundError(f"Agent {query.agent_id} not found")
        return AgentDTO.from_domain(agent)


class ListActiveAgentsHandler(QueryHandler[ListActiveAgents, list[AgentDTO]]):
    async def handle(
        self, query: ListActiveAgents, context: ExecutionContext
    ) -> list[AgentDTO]:
        await self._authz.ensure_can(context, Action.READ, ResourceType.AGENT)
        async with self._uow as uow:
            items = await uow.agents.list_active()
        return [AgentDTO.from_domain(a) for a in items]
