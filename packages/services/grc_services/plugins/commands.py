"""Commands for the Plugin Management capability."""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_domain.shared.identifiers import AgentId, PluginId, ToolId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class InstallPlugin(Command):
    name: str
    version: str
    provided_tool_ids: tuple[ToolId, ...] = field(default_factory=tuple)
    provided_agent_ids: tuple[AgentId, ...] = field(default_factory=tuple)
    required_permissions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class EnablePlugin(Command):
    plugin_id: PluginId


@dataclass(frozen=True, kw_only=True)
class DisablePlugin(Command):
    plugin_id: PluginId
