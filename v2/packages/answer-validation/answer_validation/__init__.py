"""Rasheed V2 Answer Validation Engine (Phase 13).

Validates a generated `Answer` against the existing `ContextPackage`, its citations, and the
`ResponseContract`, returning a `ValidatedAnswer`. It only validates — it never generates,
retrieves, or mutates the answer. Depends only on pipeline-contracts.
"""

from answer_validation.models import (
    ConfidencePenalty,
    ValidatedAnswer,
    ValidationCode,
    ValidationIssue,
    ValidationSeverity,
    ValidationStatus,
    default_severity,
)
from answer_validation.validator import AnswerValidator

__all__ = [
    "AnswerValidator",
    "ValidatedAnswer",
    "ValidationStatus",
    "ValidationSeverity",
    "ValidationCode",
    "ValidationIssue",
    "ConfidencePenalty",
    "default_severity",
]
