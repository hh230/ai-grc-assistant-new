"""Use cases for the Plugin Management capability."""

from __future__ import annotations

from grc_domain.platform.entities import PluginDescriptor
from grc_domain.platform.value_objects import Permission
from grc_domain.shared.identifiers import PluginId
from grc_domain.shared.value_objects import SemanticVersion

from ..shared.authorization import Action, ResourceType
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import DisablePlugin, EnablePlugin, InstallPlugin
from .dtos import PluginDTO
from .queries import GetPlugin, ListPlugins


async def _load(uow: UnitOfWork, plugin_id: PluginId) -> PluginDescriptor:
    plugin = await uow.plugins.get(plugin_id)
    if plugin is None:
        raise ResourceNotFoundError(f"Plugin {plugin_id} not found")
    return plugin


class InstallPluginHandler(TransactionalCommandHandler[InstallPlugin, PluginDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.PLUGIN)
        plugin = PluginDescriptor.install(
            id=PluginId.generate(),
            name=command.name,
            version=SemanticVersion.parse(command.version),
            provided_tool_ids=frozenset(command.provided_tool_ids),
            provided_agent_ids=frozenset(command.provided_agent_ids),
            required_permissions=frozenset(
                Permission(name) for name in command.required_permissions
            ),
        )
        await uow.plugins.add(plugin)
        return PluginDTO.from_domain(plugin)


class EnablePluginHandler(TransactionalCommandHandler[EnablePlugin, PluginDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.PLUGIN, str(command.plugin_id)
        )
        plugin = await _load(uow, command.plugin_id)
        plugin.enable()
        await uow.plugins.save(plugin)
        return PluginDTO.from_domain(plugin)


class DisablePluginHandler(TransactionalCommandHandler[DisablePlugin, PluginDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.PLUGIN, str(command.plugin_id)
        )
        plugin = await _load(uow, command.plugin_id)
        plugin.disable()
        await uow.plugins.save(plugin)
        return PluginDTO.from_domain(plugin)


class GetPluginHandler(QueryHandler[GetPlugin, PluginDTO]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.PLUGIN, str(query.plugin_id)
        )
        async with self._uow as uow:
            plugin = await uow.plugins.get(query.plugin_id)
        if plugin is None:
            raise ResourceNotFoundError(f"Plugin {query.plugin_id} not found")
        return PluginDTO.from_domain(plugin)


class ListPluginsHandler(QueryHandler[ListPlugins, list[PluginDTO]]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.READ, ResourceType.PLUGIN)
        async with self._uow as uow:
            items = await uow.plugins.list_installed()
        return [PluginDTO.from_domain(p) for p in items]
