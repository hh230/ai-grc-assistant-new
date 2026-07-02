"""Domain services for the Assessments bounded context.

`CoverageCalculatorService` is a pure function over assessment results.
"""
from __future__ import annotations

from collections.abc import Iterable

from .enums import CoverageLevel
from .value_objects import ControlAssessmentResult, CoverageSummary


class CoverageCalculatorService:
    @staticmethod
    def summarize(results: Iterable[ControlAssessmentResult]) -> CoverageSummary:
        covered = partial = not_covered = not_applicable = total = 0
        for result in results:
            total += 1
            if result.coverage is CoverageLevel.COVERED:
                covered += 1
            elif result.coverage is CoverageLevel.PARTIALLY_COVERED:
                partial += 1
            elif result.coverage is CoverageLevel.NOT_COVERED:
                not_covered += 1
            else:
                not_applicable += 1
        return CoverageSummary(
            total=total,
            covered=covered,
            partially_covered=partial,
            not_covered=not_covered,
            not_applicable=not_applicable,
        )
