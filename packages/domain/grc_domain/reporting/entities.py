"""Aggregate root for the Reporting bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.entity import AggregateRoot
from ..shared.identifiers import (
    AssessmentId,
    MissionId,
    OrganizationId,
    ReportId,
)
from .enums import ReportStatus, ReportType
from .events import ReportFinalized, ReportGenerated, ReportPublished, ReportRequested
from .exceptions import IllegalReportTransition
from .value_objects import ReportSection


@dataclass(kw_only=True, eq=False)
class Report(AggregateRoot):
    id: ReportId
    organization_id: OrganizationId
    report_type: ReportType
    title: str
    status: ReportStatus = ReportStatus.REQUESTED
    source_mission_id: MissionId | None = None
    source_assessment_id: AssessmentId | None = None
    sections: tuple[ReportSection, ...] = field(default_factory=tuple)

    @classmethod
    def request(
        cls,
        *,
        id: ReportId,
        organization_id: OrganizationId,
        report_type: ReportType,
        title: str,
        source_mission_id: MissionId | None = None,
        source_assessment_id: AssessmentId | None = None,
    ) -> Report:
        report = cls(
            id=id,
            organization_id=organization_id,
            report_type=report_type,
            title=title,
            source_mission_id=source_mission_id,
            source_assessment_id=source_assessment_id,
        )
        report._record_event(ReportRequested(report_id=id, organization_id=organization_id))
        return report

    def attach_content(self, sections: tuple[ReportSection, ...]) -> None:
        if self.status not in (ReportStatus.REQUESTED, ReportStatus.GENERATED):
            raise IllegalReportTransition("Content can only be attached before finalization")
        self.sections = sections
        self.status = ReportStatus.GENERATED
        self._record_event(ReportGenerated(report_id=self.id))

    def finalize(self) -> None:
        if self.status is not ReportStatus.GENERATED:
            raise IllegalReportTransition("Only a generated report can be finalized")
        self.status = ReportStatus.FINALIZED
        self._record_event(ReportFinalized(report_id=self.id))

    def publish(self) -> None:
        if self.status is not ReportStatus.FINALIZED:
            raise IllegalReportTransition("Only a finalized report can be published")
        self.status = ReportStatus.PUBLISHED
        self._record_event(ReportPublished(report_id=self.id))
