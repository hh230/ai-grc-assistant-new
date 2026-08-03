"""Rasheed V2 **Governance Session** service (ADR 0066) — the thin orchestration layer between the
pure `governance-discovery` engine and `governance-store` persistence: start / answer / go-back /
resume, exactly the operations the discovery API needs.
"""

from governance_session.errors import (
    GovernanceSessionError,
    InvalidAnswer,
    NoQuestionToGoBackTo,
    QuestionNotCurrentlyEligible,
    SessionAlreadyConcluded,
    SessionNotFound,
    UnknownQuestion,
)
from governance_session.service import AnswerOutcome, DiscoverySessionService, GoBackTarget

__all__ = [
    "DiscoverySessionService",
    "AnswerOutcome",
    "GoBackTarget",
    "GovernanceSessionError",
    "SessionNotFound",
    "SessionAlreadyConcluded",
    "UnknownQuestion",
    "QuestionNotCurrentlyEligible",
    "InvalidAnswer",
    "NoQuestionToGoBackTo",
]
