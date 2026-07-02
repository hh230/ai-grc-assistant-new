"""Use cases for the Tool Management capability (the governance view of the Tool Registry)."""

from __future__ import annotations

from grc_domain.platform.entities import ToolDescriptor
from grc_domain.platform.value_objects import Permission
from grc_domain.shared.identifiers import ToolId
from grc_domain.shared.value_objects import SemanticVersion

from ..shared.authorization import Action, ResourceType
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from .commands import DeprecateTool, RegisterTool
from .dtos import ToolDTO
from .queries import GetTool, ListActiveTools


class RegisterToolHandler(TransactionalCommandHandler[RegisterTool, ToolDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.TOOL)
        tool = ToolDescriptor.register(
            id=ToolId.generate(),
            name=command.name,
            version=SemanticVersion.parse(command.version),
            description=command.description,
            side_effect=command.side_effect,
            required_permissions=frozenset(
                Permission(name) for name in command.required_permissions
            ),
        )
        await uow.tools.add(tool)
        return ToolDTO.from_domain(tool)


class DeprecateToolHandler(TransactionalCommandHandler[DeprecateTool, ToolDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.TOOL, str(command.tool_id)
        )
        tool = await uow.tools.get(command.tool_id)
        if tool is None:
            raise ResourceNotFoundError(f"Tool {command.tool_id} not found")
        tool.deprecate()
        await uow.tools.save(tool)
        return ToolDTO.from_domain(tool)


class GetToolHandler(QueryHandler[GetTool, ToolDTO]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.READ, ResourceType.TOOL, str(query.tool_id))
        async with self._uow as uow:
            tool = await uow.tools.get(query.tool_id)
        if tool is None:
            raise ResourceNotFoundError(f"Tool {query.tool_id} not found")
        return ToolDTO.from_domain(tool)


class ListActiveToolsHandler(QueryHandler[ListActiveTools, list[ToolDTO]]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.READ, ResourceType.TOOL)
        async with self._uow as uow:
            items = await uow.tools.list_active()
        return [ToolDTO.from_domain(t) for t in items]
