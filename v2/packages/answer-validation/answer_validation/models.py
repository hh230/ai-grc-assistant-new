"""The validation engine's output contract: the issue taxonomy and the `ValidatedAnswer`.

`ValidatedAnswer` wraps the *unchanged* `Answer` (reused from pipeline-contracts — never a
copy) with a verdict: a status, the issues found (each an error or a warning), and a
*suggested* confidence adjustment. The adjustment is advice for a later phase, never applied
here — this engine does not touch the answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pipeline_contracts import Answer, dataclass_dict


class ValidationSeverity(str, Enum):
    ERROR = "error"      # the answer is unusable/ungrounded as-is (fail-safe: stop, escalate)
    WARNING = "warning"  # a quality/structure concern worth surfacing, not disqualifying


class ValidationCode(str, Enum):
    """The finite, deterministic set of things this engine checks. Each maps to one
    severity by default (see `_DEFAULT_SEVERITY`)."""

    EMPTY_ANSWER = "empty_answer"
    MISSING_CITATIONS = "missing_citations"          # required + evidence existed, none cited
    MALFORMED_CITATION = "malformed_citation"        # a marker that isn't the [S<n>] style
    UNKNOWN_CITATION = "unknown_citation"            # cites [S<n>] absent from the ContextPackage
    MISSING_CONFIDENCE = "missing_confidence"        # required but no confidence stated
    UNSUPPORTED_CONFIDENCE = "unsupported_confidence"  # stated value not high/medium/low
    MISSING_SECTION = "missing_section"              # a required section heading is absent


class ValidationStatus(str, Enum):
    PASSED = "passed"        # no errors, no warnings
    WARNINGS = "warnings"    # no errors, ≥1 warning
    FAILED = "failed"        # ≥1 error


@dataclass(frozen=True)
class ValidationIssue:
    """One finding. `code` is the machine-stable category; `message` is human-readable;
    `detail` carries the specifics (the offending marker, the missing section name, …)."""

    code: ValidationCode
    severity: ValidationSeverity
    message: str
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class ValidatedAnswer:
    """The verdict on one generated answer. `answer` is the original, untouched. `status`
    summarizes; `issues` lists every finding; `confidence_adjustment` (≤ 0) is a *suggested*
    downward nudge a later phase may apply — this engine applies nothing."""

    answer: Answer
    status: ValidationStatus
    issues: tuple[ValidationIssue, ...] = ()
    confidence_adjustment: float = 0.0

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity is ValidationSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity is ValidationSeverity.WARNING)

    @property
    def is_valid(self) -> bool:
        """True unless a hard error was found. Warnings do not invalidate an answer."""
        return self.status is not ValidationStatus.FAILED

    def to_dict(self) -> dict[str, object]:
        return {
            "answer": self.answer.to_dict(),
            "status": self.status.value,
            "is_valid": self.is_valid,
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
            "confidence_adjustment": round(self.confidence_adjustment, 4),
        }


_DEFAULT_SEVERITY: dict[ValidationCode, ValidationSeverity] = {
    ValidationCode.EMPTY_ANSWER: ValidationSeverity.ERROR,
    ValidationCode.MISSING_CITATIONS: ValidationSeverity.ERROR,
    ValidationCode.UNKNOWN_CITATION: ValidationSeverity.ERROR,
    ValidationCode.MALFORMED_CITATION: ValidationSeverity.WARNING,
    ValidationCode.MISSING_CONFIDENCE: ValidationSeverity.WARNING,
    ValidationCode.UNSUPPORTED_CONFIDENCE: ValidationSeverity.WARNING,
    ValidationCode.MISSING_SECTION: ValidationSeverity.WARNING,
}


def default_severity(code: ValidationCode) -> ValidationSeverity:
    return _DEFAULT_SEVERITY[code]


@dataclass(frozen=True)
class ConfidencePenalty:
    """How much each error category suggests lowering confidence. Tunable, bounded, and
    injectable so the policy is explicit rather than scattered magic numbers."""

    missing_citations: float = 0.5
    per_unknown_citation: float = 0.3
    per_warning: float = 0.05
    floor: float = -1.0
