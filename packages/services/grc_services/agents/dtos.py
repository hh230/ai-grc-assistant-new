"""DTOs for the Agent Management capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.platform.entities import AgentDescriptor

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class AgentDTO(DataTransferObject):
    id: str
    name: str
    agent_type: str
    status: str
    allowed_tool_ids: tuple[str, ...]
    data_scopes: tuple[str, ...]

    @classmethod
    def from_domain(cls, a: AgentDescriptor) -> AgentDTO:
        return cls(
            id=str(a.id),
            name=a.name,
            agent_type=a.agent_type.value,
            status=a.status.value,
            allowed_tool_ids=tuple(str(t) for t in a.allowed_tool_ids),
            data_scopes=tuple(a.data_scopes),
        )
