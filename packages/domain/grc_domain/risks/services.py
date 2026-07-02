"""Domain services for the Risks bounded context.

`RiskScoringService` is pure: it turns a (likelihood, impact) pair into a score and a
qualitative level using a deterministic matrix. No I/O, no AI.
"""
from __future__ import annotations

from .enums import RiskImpact, RiskLevel, RiskLikelihood
from .value_objects import RiskScore


class RiskScoringService:
    @staticmethod
    def _level_for(value: int) -> RiskLevel:
        if value <= 4:
            return RiskLevel.LOW
        if value <= 9:
            return RiskLevel.MEDIUM
        if value <= 16:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    @classmethod
    def score(cls, likelihood: RiskLikelihood, impact: RiskImpact) -> RiskScore:
        value = int(likelihood) * int(impact)
        return RiskScore(
            value=value,
            level=cls._level_for(value),
            likelihood=likelihood,
            impact=impact,
        )
