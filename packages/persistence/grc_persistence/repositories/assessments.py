"""Repository for the Assessments context."""

from __future__ import annotations

from grc_domain.assessments.entities import Assessment
from grc_domain.assessments.repositories import AssessmentRepository
from grc_domain.shared.identifiers import AssessmentId, OrganizationId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.assessments import assessment_mapper
from ..models.assessments import AssessmentModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyAssessmentRepository(
    SqlAlchemyAggregateRepository[Assessment, AssessmentModel], AssessmentRepository
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, assessment_mapper, tracker, cache, AssessmentModel)

    async def get(
        self, organization_id: OrganizationId, assessment_id: AssessmentId
    ) -> Assessment | None:
        return await self._get_by(
            self._key(str(assessment_id), str(organization_id)),
            AssessmentModel.id == str(assessment_id),
            AssessmentModel.organization_id == str(organization_id),
        )

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Assessment]:
        return await self._list_by(
            AssessmentModel.organization_id == str(organization_id),
            order_by=AssessmentModel.created_at,
        )

    async def add(self, assessment: Assessment) -> None:
        await self._insert(
            assessment, self._key(str(assessment.id), str(assessment.organization_id))
        )

    async def save(self, assessment: Assessment) -> None:
        await self._update(
            assessment,
            self._key(str(assessment.id), str(assessment.organization_id)),
            pk=str(assessment.id),
            tenant=str(assessment.organization_id),
        )
