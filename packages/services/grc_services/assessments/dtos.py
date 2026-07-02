"""DTOs for the Assessment capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.assessments.entities import Assessment

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class CoverageSummaryDTO(DataTransferObject):
    total: int
    covered: int
    partially_covered: int
    not_covered: int
    not_applicable: int
    coverage_ratio: float


@dataclass(frozen=True)
class AssessmentDTO(DataTransferObject):
    id: str
    organization_id: str
    workspace_id: str
    framework_id: str
    framework_version: str
    assessment_type: str
    status: str
    result_count: int
    summary: CoverageSummaryDTO | None

    @classmethod
    def from_domain(cls, a: Assessment) -> AssessmentDTO:
        summary = None
        if a.summary is not None:
            summary = CoverageSummaryDTO(
                total=a.summary.total,
                covered=a.summary.covered,
                partially_covered=a.summary.partially_covered,
                not_covered=a.summary.not_covered,
                not_applicable=a.summary.not_applicable,
                coverage_ratio=a.summary.coverage_ratio,
            )
        return cls(
            id=str(a.id),
            organization_id=str(a.organization_id),
            workspace_id=str(a.workspace_id),
            framework_id=str(a.framework_id),
            framework_version=str(a.framework_version),
            assessment_type=a.assessment_type.value,
            status=a.status.value,
            result_count=len(a.results),
            summary=summary,
        )
