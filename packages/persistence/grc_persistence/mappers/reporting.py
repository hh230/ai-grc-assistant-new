"""Mapper for the Reporting context."""

from __future__ import annotations

from grc_domain.reporting.entities import Report
from grc_domain.reporting.enums import ReportStatus, ReportType
from grc_domain.shared.identifiers import (
    AssessmentId,
    MissionId,
    OrganizationId,
    ReportId,
)

from ..contracts.mapper import AggregateMapper
from ..models.reporting import ReportModel
from ._common import aware, decode_report_section, encode_report_section


class ReportMapper(AggregateMapper[Report, ReportModel]):
    def to_orm(self, aggregate: Report) -> ReportModel:
        return ReportModel(
            id=str(aggregate.id),
            organization_id=str(aggregate.organization_id),
            report_type=aggregate.report_type.value,
            title=aggregate.title,
            status=aggregate.status.value,
            source_mission_id=(
                str(aggregate.source_mission_id)
                if aggregate.source_mission_id is not None
                else None
            ),
            source_assessment_id=(
                str(aggregate.source_assessment_id)
                if aggregate.source_assessment_id is not None
                else None
            ),
            sections=[encode_report_section(section) for section in aggregate.sections],
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: ReportModel, aggregate: Report) -> None:
        model.title = aggregate.title
        model.status = aggregate.status.value
        model.sections = [encode_report_section(section) for section in aggregate.sections]
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: ReportModel) -> Report:
        return Report(
            id=ReportId(model.id),
            organization_id=OrganizationId(model.organization_id),
            report_type=ReportType(model.report_type),
            title=model.title,
            status=ReportStatus(model.status),
            source_mission_id=(
                MissionId(model.source_mission_id) if model.source_mission_id is not None else None
            ),
            source_assessment_id=(
                AssessmentId(model.source_assessment_id)
                if model.source_assessment_id is not None
                else None
            ),
            sections=tuple(decode_report_section(item) for item in model.sections),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


report_mapper = ReportMapper()
