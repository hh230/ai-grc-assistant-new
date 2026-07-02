"""Aggregate root for the Assessments bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..frameworks.value_objects import FrameworkVersion
from ..shared.entity import AggregateRoot
from ..shared.identifiers import (
    AssessmentId,
    FrameworkId,
    OrganizationId,
    WorkspaceId,
)
from .enums import AssessmentStatus, AssessmentType
from .events import AssessmentCompleted, AssessmentStarted, ControlAssessed
from .exceptions import IllegalAssessmentTransition
from .services import CoverageCalculatorService
from .value_objects import ControlAssessmentResult, CoverageSummary


@dataclass(kw_only=True, eq=False)
class Assessment(AggregateRoot):
    """An assessment of an organization against a pinned framework version."""

    id: AssessmentId
    organization_id: OrganizationId
    workspace_id: WorkspaceId
    framework_id: FrameworkId
    framework_version: FrameworkVersion
    assessment_type: AssessmentType = AssessmentType.GAP_ANALYSIS
    status: AssessmentStatus = AssessmentStatus.PLANNED
    results: list[ControlAssessmentResult] = field(default_factory=list)
    summary: CoverageSummary | None = None

    @classmethod
    def plan(
        cls,
        *,
        id: AssessmentId,
        organization_id: OrganizationId,
        workspace_id: WorkspaceId,
        framework_id: FrameworkId,
        framework_version: FrameworkVersion,
        assessment_type: AssessmentType = AssessmentType.GAP_ANALYSIS,
    ) -> Assessment:
        return cls(
            id=id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            framework_id=framework_id,
            framework_version=framework_version,
            assessment_type=assessment_type,
        )

    def start(self) -> None:
        if self.status is not AssessmentStatus.PLANNED:
            raise IllegalAssessmentTransition("Only a planned assessment can be started")
        self.status = AssessmentStatus.IN_PROGRESS
        self._record_event(
            AssessmentStarted(
                assessment_id=self.id,
                organization_id=self.organization_id,
                framework_id=self.framework_id,
            )
        )

    def record_result(self, result: ControlAssessmentResult) -> None:
        if self.status is not AssessmentStatus.IN_PROGRESS:
            raise IllegalAssessmentTransition("Results can only be recorded while in progress")
        self.results.append(result)
        self._touch()
        self._record_event(
            ControlAssessed(
                assessment_id=self.id, framework_control_id=result.framework_control_id
            )
        )

    def complete(self) -> None:
        if self.status is not AssessmentStatus.IN_PROGRESS:
            raise IllegalAssessmentTransition("Only an in-progress assessment can be completed")
        self.summary = CoverageCalculatorService.summarize(self.results)
        self.status = AssessmentStatus.COMPLETED
        self._record_event(AssessmentCompleted(assessment_id=self.id, summary=self.summary))

    def cancel(self) -> None:
        if self.status in (AssessmentStatus.COMPLETED, AssessmentStatus.CANCELLED):
            raise IllegalAssessmentTransition("Assessment already finalized")
        self.status = AssessmentStatus.CANCELLED
