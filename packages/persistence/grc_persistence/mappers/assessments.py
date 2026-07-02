"""Mapper for the Assessments context."""

from __future__ import annotations

from grc_domain.assessments.entities import Assessment
from grc_domain.assessments.enums import AssessmentStatus, AssessmentType
from grc_domain.frameworks.value_objects import FrameworkVersion
from grc_domain.shared.identifiers import AssessmentId, FrameworkId, OrganizationId, WorkspaceId

from ..contracts.mapper import AggregateMapper
from ..models.assessments import AssessmentModel
from ._common import (
    aware,
    decode_assessment_result,
    decode_coverage_summary,
    encode_assessment_result,
    encode_coverage_summary,
)


class AssessmentMapper(AggregateMapper[Assessment, AssessmentModel]):
    def to_orm(self, aggregate: Assessment) -> AssessmentModel:
        return AssessmentModel(
            id=str(aggregate.id),
            organization_id=str(aggregate.organization_id),
            workspace_id=str(aggregate.workspace_id),
            framework_id=str(aggregate.framework_id),
            framework_version_label=str(aggregate.framework_version),
            assessment_type=aggregate.assessment_type.value,
            status=aggregate.status.value,
            results=[encode_assessment_result(result) for result in aggregate.results],
            summary=encode_coverage_summary(aggregate.summary),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: AssessmentModel, aggregate: Assessment) -> None:
        model.assessment_type = aggregate.assessment_type.value
        model.status = aggregate.status.value
        model.results = [encode_assessment_result(result) for result in aggregate.results]
        model.summary = encode_coverage_summary(aggregate.summary)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: AssessmentModel) -> Assessment:
        return Assessment(
            id=AssessmentId(model.id),
            organization_id=OrganizationId(model.organization_id),
            workspace_id=WorkspaceId(model.workspace_id),
            framework_id=FrameworkId(model.framework_id),
            framework_version=FrameworkVersion(model.framework_version_label),
            assessment_type=AssessmentType(model.assessment_type),
            status=AssessmentStatus(model.status),
            results=[decode_assessment_result(item) for item in model.results],
            summary=decode_coverage_summary(model.summary),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


assessment_mapper = AssessmentMapper()
