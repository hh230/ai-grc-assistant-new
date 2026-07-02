"""Domain events for the Risks bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import OrganizationId, RiskId, UserId
from .enums import RiskTreatment
from .value_objects import RiskScore


@dataclass(frozen=True, kw_only=True)
class RiskIdentified(DomainEvent):
    risk_id: RiskId
    organization_id: OrganizationId
    title: str


@dataclass(frozen=True, kw_only=True)
class RiskAssessed(DomainEvent):
    risk_id: RiskId
    score: RiskScore


@dataclass(frozen=True, kw_only=True)
class RiskTreatmentPlanned(DomainEvent):
    risk_id: RiskId
    treatment: RiskTreatment


@dataclass(frozen=True, kw_only=True)
class RiskAccepted(DomainEvent):
    """Consequential action — only emitted after an explicit human approval."""

    risk_id: RiskId
    accepted_by: UserId
    rationale: str


@dataclass(frozen=True, kw_only=True)
class RiskClosed(DomainEvent):
    risk_id: RiskId
