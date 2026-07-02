"""Commands for the Reporting capability."""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_domain.reporting.enums import ReportType
from grc_domain.reporting.value_objects import ReportSection
from grc_domain.shared.identifiers import AssessmentId, MissionId, ReportId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class RequestReport(Command):
    report_type: ReportType
    title: str
    source_mission_id: MissionId | None = None
    source_assessment_id: AssessmentId | None = None


@dataclass(frozen=True, kw_only=True)
class AttachReportContent(Command):
    report_id: ReportId
    sections: tuple[ReportSection, ...] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class FinalizeReport(Command):
    report_id: ReportId


@dataclass(frozen=True, kw_only=True)
class PublishReport(Command):
    report_id: ReportId
