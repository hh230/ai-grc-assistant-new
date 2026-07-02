"""Value objects for the Risks bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from .enums import RiskImpact, RiskLevel, RiskLikelihood


@dataclass(frozen=True)
class RiskScore:
    """A computed risk score (likelihood x impact) with a derived qualitative level."""

    value: int
    level: RiskLevel
    likelihood: RiskLikelihood
    impact: RiskImpact
