"""Domain events for the Evidence bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import EvidenceId, OrganizationId, UserId


@dataclass(frozen=True, kw_only=True)
class EvidenceCollected(DomainEvent):
    evidence_id: EvidenceId
    organization_id: OrganizationId


@dataclass(frozen=True, kw_only=True)
class EvidenceValidated(DomainEvent):
    evidence_id: EvidenceId
    validated_by: UserId


@dataclass(frozen=True, kw_only=True)
class EvidenceRejected(DomainEvent):
    evidence_id: EvidenceId
    reason: str


@dataclass(frozen=True, kw_only=True)
class EvidenceExpired(DomainEvent):
    evidence_id: EvidenceId
