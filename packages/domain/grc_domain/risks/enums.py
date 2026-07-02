"""Enumerations for the Risks bounded context."""
from __future__ import annotations

from enum import Enum


class RiskLikelihood(int, Enum):
    RARE = 1
    UNLIKELY = 2
    POSSIBLE = 3
    LIKELY = 4
    ALMOST_CERTAIN = 5


class RiskImpact(int, Enum):
    NEGLIGIBLE = 1
    MINOR = 2
    MODERATE = 3
    MAJOR = 4
    SEVERE = 5


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(str, Enum):
    IDENTIFIED = "identified"
    ASSESSED = "assessed"
    TREATMENT_PLANNED = "treatment_planned"
    ACCEPTED = "accepted"
    CLOSED = "closed"


class RiskTreatment(str, Enum):
    MITIGATE = "mitigate"
    TRANSFER = "transfer"
    AVOID = "avoid"
    ACCEPT = "accept"
