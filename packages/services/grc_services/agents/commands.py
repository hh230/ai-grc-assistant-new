"""Commands for the Agent Management capability."""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_domain.platform.enums import AgentType
from grc_domain.shared.identifiers import ToolId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class RegisterAgent(Command):
    name: str
    agent_type: AgentType
    allowed_tool_ids: tuple[ToolId, ...] = field(default_factory=tuple)
    data_scopes: tuple[str, ...] = field(default_factory=tuple)
