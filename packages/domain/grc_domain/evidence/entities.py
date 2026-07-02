"""Aggregate root for the Evidence bounded context.

Evidence is an artifact proving a control is operating. The actual file/content lives in
a knowledge source / object store (infrastructure); here we model only its domain state
and lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..shared.entity import AggregateRoot
from ..shared.identifiers import (
    ControlId,
    EvidenceId,
    KnowledgeSourceId,
    OrganizationId,
    UserId,
)
from ..shared.value_objects import DateRange
from .enums import EvidenceStatus, EvidenceType
from .events import (
    EvidenceCollected,
    EvidenceExpired,
    EvidenceRejected,
    EvidenceValidated,
)
from .exceptions import IllegalEvidenceTransition


@dataclass(kw_only=True, eq=False)
class Evidence(AggregateRoot):
    id: EvidenceId
    organization_id: OrganizationId
    title: str
    evidence_type: EvidenceType
    knowledge_source_id: KnowledgeSourceId | None = None
    collected_at: datetime | None = None
    validity: DateRange | None = None
    status: EvidenceStatus = EvidenceStatus.COLLECTED
    linked_control_ids: set[ControlId] = field(default_factory=set)
    rejection_reason: str | None = None

    @classmethod
    def collect(
        cls,
        *,
        id: EvidenceId,
        organization_id: OrganizationId,
        title: str,
        evidence_type: EvidenceType,
        knowledge_source_id: KnowledgeSourceId | None = None,
        collected_at: datetime | None = None,
        validity: DateRange | None = None,
    ) -> Evidence:
        if not title.strip():
            raise ValueError("Evidence title must not be empty")
        evidence = cls(
            id=id,
            organization_id=organization_id,
            title=title,
            evidence_type=evidence_type,
            knowledge_source_id=knowledge_source_id,
            collected_at=collected_at,
            validity=validity,
        )
        evidence._record_event(
            EvidenceCollected(evidence_id=id, organization_id=organization_id)
        )
        return evidence

    def validate(self, *, validated_by: UserId) -> None:
        if self.status is not EvidenceStatus.COLLECTED:
            raise IllegalEvidenceTransition("Only collected evidence can be validated")
        self.status = EvidenceStatus.VALIDATED
        self._record_event(EvidenceValidated(evidence_id=self.id, validated_by=validated_by))

    def reject(self, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Rejection reason must not be empty")
        self.status = EvidenceStatus.REJECTED
        self.rejection_reason = reason
        self._record_event(EvidenceRejected(evidence_id=self.id, reason=reason))

    def mark_expired(self) -> None:
        if self.status is EvidenceStatus.REJECTED:
            raise IllegalEvidenceTransition("Rejected evidence cannot expire")
        self.status = EvidenceStatus.EXPIRED
        self._record_event(EvidenceExpired(evidence_id=self.id))

    def link_control(self, control_id: ControlId) -> None:
        if control_id not in self.linked_control_ids:
            self.linked_control_ids.add(control_id)
            self._touch()
