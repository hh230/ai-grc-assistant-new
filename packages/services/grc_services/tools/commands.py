"""Commands for the Tool Management capability."""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_domain.platform.enums import ToolSideEffect
from grc_domain.shared.identifiers import ToolId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class RegisterTool(Command):
    name: str
    version: str
    description: str
    side_effect: ToolSideEffect
    required_permissions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class DeprecateTool(Command):
    tool_id: ToolId
