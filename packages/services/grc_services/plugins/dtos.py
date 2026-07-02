"""DTOs for the Plugin Management capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.platform.entities import PluginDescriptor

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class PluginDTO(DataTransferObject):
    id: str
    name: str
    version: str
    status: str
    provided_tool_ids: tuple[str, ...]
    provided_agent_ids: tuple[str, ...]

    @classmethod
    def from_domain(cls, p: PluginDescriptor) -> PluginDTO:
        return cls(
            id=str(p.id),
            name=p.name,
            version=str(p.version),
            status=p.status.value,
            provided_tool_ids=tuple(str(t) for t in p.provided_tool_ids),
            provided_agent_ids=tuple(str(a) for a in p.provided_agent_ids),
        )
