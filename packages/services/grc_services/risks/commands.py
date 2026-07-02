"""Commands for the Risk capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.risks.enums import RiskImpact, RiskLikelihood, RiskTreatment
from grc_domain.shared.identifiers import RiskId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class IdentifyRisk(Command):
    title: str
    description: str | None = None
    category: str | None = None


@dataclass(frozen=True, kw_only=True)
class AssessRisk(Command):
    risk_id: RiskId
    likelihood: RiskLikelihood
    impact: RiskImpact


@dataclass(frozen=True, kw_only=True)
class PlanRiskTreatment(Command):
    risk_id: RiskId
    treatment: RiskTreatment


@dataclass(frozen=True, kw_only=True)
class AcceptRisk(Command):
    risk_id: RiskId
    rationale: str


@dataclass(frozen=True, kw_only=True)
class CloseRisk(Command):
    risk_id: RiskId
