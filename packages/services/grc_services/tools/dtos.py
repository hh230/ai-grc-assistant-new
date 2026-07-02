"""DTOs for the Tool Management capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.platform.entities import ToolDescriptor

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class ToolDTO(DataTransferObject):
    id: str
    name: str
    version: str
    side_effect: str
    status: str
    requires_approval: bool

    @classmethod
    def from_domain(cls, t: ToolDescriptor) -> ToolDTO:
        return cls(
            id=str(t.id),
            name=t.name,
            version=str(t.version),
            side_effect=t.side_effect.value,
            status=t.status.value,
            requires_approval=t.requires_approval,
        )
