"""Aggregate root for the Risks bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.entity import AggregateRoot
from ..shared.identifiers import ControlId, EvidenceId, OrganizationId, RiskId, UserId
from .enums import RiskImpact, RiskLikelihood, RiskStatus, RiskTreatment
from .events import (
    RiskAccepted,
    RiskAssessed,
    RiskClosed,
    RiskIdentified,
    RiskTreatmentPlanned,
)
from .exceptions import RiskAcceptanceRequiresRationale, RiskNotAssessedError
from .services import RiskScoringService
from .value_objects import RiskScore


@dataclass(kw_only=True, eq=False)
class Risk(AggregateRoot):
    id: RiskId
    organization_id: OrganizationId
    title: str
    description: str | None = None
    category: str | None = None
    owner_id: UserId | None = None
    status: RiskStatus = RiskStatus.IDENTIFIED
    score: RiskScore | None = None
    treatment: RiskTreatment | None = None
    accepted_by: UserId | None = None
    acceptance_rationale: str | None = None
    mitigating_control_ids: set[ControlId] = field(default_factory=set)
    evidence_ids: set[EvidenceId] = field(default_factory=set)

    @classmethod
    def identify(
        cls,
        *,
        id: RiskId,
        organization_id: OrganizationId,
        title: str,
        description: str | None = None,
        category: str | None = None,
        owner_id: UserId | None = None,
    ) -> Risk:
        if not title.strip():
            raise ValueError("Risk title must not be empty")
        risk = cls(
            id=id,
            organization_id=organization_id,
            title=title,
            description=description,
            category=category,
            owner_id=owner_id,
        )
        risk._record_event(
            RiskIdentified(risk_id=id, organization_id=organization_id, title=title)
        )
        return risk

    def assess(self, *, likelihood: RiskLikelihood, impact: RiskImpact) -> None:
        self.score = RiskScoringService.score(likelihood, impact)
        self.status = RiskStatus.ASSESSED
        self._record_event(RiskAssessed(risk_id=self.id, score=self.score))

    def plan_treatment(self, treatment: RiskTreatment) -> None:
        if self.status not in (RiskStatus.ASSESSED, RiskStatus.TREATMENT_PLANNED):
            raise RiskNotAssessedError("Risk must be assessed before planning treatment")
        self.treatment = treatment
        self.status = RiskStatus.TREATMENT_PLANNED
        self._record_event(RiskTreatmentPlanned(risk_id=self.id, treatment=treatment))

    def accept(self, *, approver_id: UserId, rationale: str) -> None:
        """Accept the risk. Consequential — requires an explicit approver and rationale."""
        if self.status is RiskStatus.IDENTIFIED or self.score is None:
            raise RiskNotAssessedError("Risk must be assessed before it can be accepted")
        if not rationale.strip():
            raise RiskAcceptanceRequiresRationale("Risk acceptance requires a rationale")
        self.status = RiskStatus.ACCEPTED
        self.treatment = RiskTreatment.ACCEPT
        self.accepted_by = approver_id
        self.acceptance_rationale = rationale
        self._record_event(
            RiskAccepted(risk_id=self.id, accepted_by=approver_id, rationale=rationale)
        )

    def close(self) -> None:
        self.status = RiskStatus.CLOSED
        self._record_event(RiskClosed(risk_id=self.id))
