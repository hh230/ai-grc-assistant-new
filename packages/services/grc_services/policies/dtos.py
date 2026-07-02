"""DTOs for the Policy capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.policies.entities import Policy

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class PolicyDTO(DataTransferObject):
    id: str
    organization_id: str
    title: str
    status: str
    owner_id: str
    version: int
    approved_by: str | None

    @classmethod
    def from_domain(cls, p: Policy) -> PolicyDTO:
        return cls(
            id=str(p.id),
            organization_id=str(p.organization_id),
            title=p.title,
            status=p.status.value,
            owner_id=str(p.owner_id),
            version=p.version.number,
            approved_by=str(p.approved_by) if p.approved_by else None,
        )
