"""DTOs for the Evidence capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.evidence.entities import Evidence

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class EvidenceDTO(DataTransferObject):
    id: str
    organization_id: str
    title: str
    evidence_type: str
    status: str
    knowledge_source_id: str | None
    linked_control_ids: tuple[str, ...]

    @classmethod
    def from_domain(cls, e: Evidence) -> EvidenceDTO:
        return cls(
            id=str(e.id),
            organization_id=str(e.organization_id),
            title=e.title,
            evidence_type=e.evidence_type.value,
            status=e.status.value,
            knowledge_source_id=str(e.knowledge_source_id) if e.knowledge_source_id else None,
            linked_control_ids=tuple(str(c) for c in e.linked_control_ids),
        )
