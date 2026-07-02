"""DTOs for the Audit capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.audit.entities import AuditRecord

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class AuditRecordDTO(DataTransferObject):
    id: str
    organization_id: str
    actor_kind: str
    actor_reference: str | None
    category: str
    action: str
    object_type: str
    object_id: str
    occurred_at: str
    outcome: str | None

    @classmethod
    def from_domain(cls, r: AuditRecord) -> AuditRecordDTO:
        return cls(
            id=str(r.id),
            organization_id=str(r.organization_id),
            actor_kind=r.actor.kind.value,
            actor_reference=r.actor.reference,
            category=r.category.value,
            action=r.action,
            object_type=r.object_type,
            object_id=r.object_id,
            occurred_at=r.occurred_at.isoformat(),
            outcome=r.outcome,
        )
