"""Value objects for the Assessments bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.identifiers import ControlId, FrameworkControlId
from ..shared.value_objects import Citation, Confidence
from .enums import CoverageLevel


@dataclass(frozen=True)
class ControlAssessmentResult:
    """The assessed coverage of a single framework control, with grounding."""

    framework_control_id: FrameworkControlId
    coverage: CoverageLevel
    satisfied_by_control_id: ControlId | None = None
    confidence: Confidence | None = None
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    notes: str | None = None


@dataclass(frozen=True)
class CoverageSummary:
    """Aggregate coverage statistics for an assessment."""

    total: int
    covered: int
    partially_covered: int
    not_covered: int
    not_applicable: int

    @property
    def applicable(self) -> int:
        return self.total - self.not_applicable

    @property
    def coverage_ratio(self) -> float:
        """Fraction of applicable controls fully covered, in [0, 1]."""
        if self.applicable <= 0:
            return 0.0
        return self.covered / self.applicable
