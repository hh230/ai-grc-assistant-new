"""DTOs for the Workspace capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.workspace.entities import Workspace

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class WorkspaceDTO(DataTransferObject):
    id: str
    organization_id: str
    name: str
    owner_id: str
    status: str
    description: str | None
    member_ids: tuple[str, ...]

    @classmethod
    def from_domain(cls, ws: Workspace) -> WorkspaceDTO:
        return cls(
            id=str(ws.id),
            organization_id=str(ws.organization_id),
            name=ws.name,
            owner_id=str(ws.owner_id),
            status=ws.status.value,
            description=ws.description,
            member_ids=tuple(str(m) for m in ws.member_ids),
        )
