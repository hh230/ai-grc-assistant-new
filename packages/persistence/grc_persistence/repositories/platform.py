"""Repositories for the Platform context (Tool / Agent / Plugin descriptors).

These catalog entries are global (not tenant-scoped), so the cache keys carry no tenant.
"""

from __future__ import annotations

from grc_domain.platform.entities import AgentDescriptor, PluginDescriptor, ToolDescriptor
from grc_domain.platform.enums import AgentStatus, ToolStatus
from grc_domain.platform.repositories import (
    AgentDescriptorRepository,
    PluginDescriptorRepository,
    ToolDescriptorRepository,
)
from grc_domain.shared.identifiers import AgentId, PluginId, ToolId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.platform import (
    agent_descriptor_mapper,
    plugin_descriptor_mapper,
    tool_descriptor_mapper,
)
from ..models.platform import (
    AgentDescriptorModel,
    PluginDescriptorModel,
    ToolDescriptorModel,
)
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyToolDescriptorRepository(
    SqlAlchemyAggregateRepository[ToolDescriptor, ToolDescriptorModel],
    ToolDescriptorRepository,
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, tool_descriptor_mapper, tracker, cache, ToolDescriptorModel)

    async def get(self, tool_id: ToolId) -> ToolDescriptor | None:
        return await self._get_by(self._key(str(tool_id)), ToolDescriptorModel.id == str(tool_id))

    async def find_by_name(self, name: str) -> list[ToolDescriptor]:
        return await self._list_by(
            ToolDescriptorModel.name == name, order_by=ToolDescriptorModel.version_label
        )

    async def list_active(self) -> list[ToolDescriptor]:
        return await self._list_by(
            ToolDescriptorModel.status == ToolStatus.REGISTERED.value,
            order_by=ToolDescriptorModel.name,
        )

    async def add(self, tool: ToolDescriptor) -> None:
        await self._insert(tool, self._key(str(tool.id)))

    async def save(self, tool: ToolDescriptor) -> None:
        await self._update(tool, self._key(str(tool.id)), pk=str(tool.id))


class SqlAlchemyAgentDescriptorRepository(
    SqlAlchemyAggregateRepository[AgentDescriptor, AgentDescriptorModel],
    AgentDescriptorRepository,
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, agent_descriptor_mapper, tracker, cache, AgentDescriptorModel)

    async def get(self, agent_id: AgentId) -> AgentDescriptor | None:
        return await self._get_by(
            self._key(str(agent_id)), AgentDescriptorModel.id == str(agent_id)
        )

    async def list_active(self) -> list[AgentDescriptor]:
        return await self._list_by(
            AgentDescriptorModel.status == AgentStatus.REGISTERED.value,
            order_by=AgentDescriptorModel.name,
        )

    async def add(self, agent: AgentDescriptor) -> None:
        await self._insert(agent, self._key(str(agent.id)))

    async def save(self, agent: AgentDescriptor) -> None:
        await self._update(agent, self._key(str(agent.id)), pk=str(agent.id))


class SqlAlchemyPluginDescriptorRepository(
    SqlAlchemyAggregateRepository[PluginDescriptor, PluginDescriptorModel],
    PluginDescriptorRepository,
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, plugin_descriptor_mapper, tracker, cache, PluginDescriptorModel)

    async def get(self, plugin_id: PluginId) -> PluginDescriptor | None:
        return await self._get_by(
            self._key(str(plugin_id)), PluginDescriptorModel.id == str(plugin_id)
        )

    async def list_installed(self) -> list[PluginDescriptor]:
        return await self._list_by(order_by=PluginDescriptorModel.name)

    async def add(self, plugin: PluginDescriptor) -> None:
        await self._insert(plugin, self._key(str(plugin.id)))

    async def save(self, plugin: PluginDescriptor) -> None:
        await self._update(plugin, self._key(str(plugin.id)), pk=str(plugin.id))
