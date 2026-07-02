"""Domain events for the Platform bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import AgentId, PluginId, ToolId


@dataclass(frozen=True, kw_only=True)
class ToolRegistered(DomainEvent):
    tool_id: ToolId
    name: str
    version: str


@dataclass(frozen=True, kw_only=True)
class ToolDeprecated(DomainEvent):
    tool_id: ToolId


@dataclass(frozen=True, kw_only=True)
class AgentRegistered(DomainEvent):
    agent_id: AgentId
    name: str


@dataclass(frozen=True, kw_only=True)
class PluginInstalled(DomainEvent):
    plugin_id: PluginId
    name: str
    version: str


@dataclass(frozen=True, kw_only=True)
class PluginEnabled(DomainEvent):
    plugin_id: PluginId


@dataclass(frozen=True, kw_only=True)
class PluginDisabled(DomainEvent):
    plugin_id: PluginId
