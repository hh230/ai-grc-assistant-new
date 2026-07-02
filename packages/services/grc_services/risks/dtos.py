"""DTOs for the Risk capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.risks.entities import Risk

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class RiskDTO(DataTransferObject):
    id: str
    organization_id: str
    title: str
    status: str
    score: int | None
    level: str | None
    treatment: str | None
    accepted_by: str | None

    @classmethod
    def from_domain(cls, r: Risk) -> RiskDTO:
        return cls(
            id=str(r.id),
            organization_id=str(r.organization_id),
            title=r.title,
            status=r.status.value,
            score=r.score.value if r.score else None,
            level=r.score.level.value if r.score else None,
            treatment=r.treatment.value if r.treatment else None,
            accepted_by=str(r.accepted_by) if r.accepted_by else None,
        )
