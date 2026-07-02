"""Aggregate roots for the Platform bounded context.

These are the *governance* descriptors of tools, agents, and plugins — the domain's view
of the catalog (CLAUDE.md §9-§11, §17). The executable implementations live elsewhere; the
domain only models identity, capability metadata, permissions, and lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.entity import AggregateRoot
from ..shared.identifiers import AgentId, PluginId, ToolId
from ..shared.value_objects import SemanticVersion
from .enums import (
    AgentStatus,
    AgentType,
    PluginStatus,
    ToolSideEffect,
    ToolStatus,
)
from .events import (
    AgentRegistered,
    PluginDisabled,
    PluginEnabled,
    PluginInstalled,
    ToolDeprecated,
    ToolRegistered,
)
from .value_objects import Permission, SchemaRef, VersionRange


@dataclass(kw_only=True, eq=False)
class ToolDescriptor(AggregateRoot):
    """Catalog entry for a tool: what it is, what it affects, and what it requires."""

    id: ToolId
    name: str
    version: SemanticVersion
    description: str
    side_effect: ToolSideEffect
    status: ToolStatus = ToolStatus.REGISTERED
    requires_approval: bool = False
    required_permissions: frozenset[Permission] = field(default_factory=frozenset)
    input_schema: SchemaRef | None = None
    output_schema: SchemaRef | None = None

    @classmethod
    def register(
        cls,
        *,
        id: ToolId,
        name: str,
        version: SemanticVersion,
        description: str,
        side_effect: ToolSideEffect,
        required_permissions: frozenset[Permission] = frozenset(),
        input_schema: SchemaRef | None = None,
        output_schema: SchemaRef | None = None,
    ) -> ToolDescriptor:
        # Consequential tools always require a human approval gate (CLAUDE.md §9).
        requires_approval = side_effect is ToolSideEffect.CONSEQUENTIAL
        tool = cls(
            id=id,
            name=name,
            version=version,
            description=description,
            side_effect=side_effect,
            requires_approval=requires_approval,
            required_permissions=required_permissions,
            input_schema=input_schema,
            output_schema=output_schema,
        )
        tool._record_event(ToolRegistered(tool_id=id, name=name, version=str(version)))
        return tool

    def deprecate(self) -> None:
        self.status = ToolStatus.DEPRECATED
        self._record_event(ToolDeprecated(tool_id=self.id))


@dataclass(kw_only=True, eq=False)
class AgentDescriptor(AggregateRoot):
    """Catalog entry for an agent and the tools/scopes it is permitted to use."""

    id: AgentId
    name: str
    agent_type: AgentType
    status: AgentStatus = AgentStatus.REGISTERED
    allowed_tool_ids: frozenset[ToolId] = field(default_factory=frozenset)
    data_scopes: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def register(
        cls,
        *,
        id: AgentId,
        name: str,
        agent_type: AgentType,
        allowed_tool_ids: frozenset[ToolId] = frozenset(),
        data_scopes: frozenset[str] = frozenset(),
    ) -> AgentDescriptor:
        agent = cls(
            id=id,
            name=name,
            agent_type=agent_type,
            allowed_tool_ids=allowed_tool_ids,
            data_scopes=data_scopes,
        )
        agent._record_event(AgentRegistered(agent_id=id, name=name))
        return agent

    def may_use(self, tool_id: ToolId) -> bool:
        return tool_id in self.allowed_tool_ids


@dataclass(kw_only=True, eq=False)
class PluginDescriptor(AggregateRoot):
    """Catalog entry for an installed plugin and the capabilities it provides."""

    id: PluginId
    name: str
    version: SemanticVersion
    status: PluginStatus = PluginStatus.INSTALLED
    provided_tool_ids: frozenset[ToolId] = field(default_factory=frozenset)
    provided_agent_ids: frozenset[AgentId] = field(default_factory=frozenset)
    required_permissions: frozenset[Permission] = field(default_factory=frozenset)
    compatibility: VersionRange | None = None

    @classmethod
    def install(
        cls,
        *,
        id: PluginId,
        name: str,
        version: SemanticVersion,
        provided_tool_ids: frozenset[ToolId] = frozenset(),
        provided_agent_ids: frozenset[AgentId] = frozenset(),
        required_permissions: frozenset[Permission] = frozenset(),
        compatibility: VersionRange | None = None,
    ) -> PluginDescriptor:
        plugin = cls(
            id=id,
            name=name,
            version=version,
            provided_tool_ids=provided_tool_ids,
            provided_agent_ids=provided_agent_ids,
            required_permissions=required_permissions,
            compatibility=compatibility,
        )
        plugin._record_event(PluginInstalled(plugin_id=id, name=name, version=str(version)))
        return plugin

    def enable(self) -> None:
        self.status = PluginStatus.ENABLED
        self._record_event(PluginEnabled(plugin_id=self.id))

    def disable(self) -> None:
        self.status = PluginStatus.DISABLED
        self._record_event(PluginDisabled(plugin_id=self.id))
