"""Repository for the Reporting context."""

from __future__ import annotations

from grc_domain.reporting.entities import Report
from grc_domain.reporting.repositories import ReportRepository
from grc_domain.shared.identifiers import OrganizationId, ReportId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.reporting import report_mapper
from ..models.reporting import ReportModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyReportRepository(
    SqlAlchemyAggregateRepository[Report, ReportModel], ReportRepository
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, report_mapper, tracker, cache, ReportModel)

    async def get(self, organization_id: OrganizationId, report_id: ReportId) -> Report | None:
        return await self._get_by(
            self._key(str(report_id), str(organization_id)),
            ReportModel.id == str(report_id),
            ReportModel.organization_id == str(organization_id),
        )

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Report]:
        return await self._list_by(
            ReportModel.organization_id == str(organization_id),
            order_by=ReportModel.created_at,
        )

    async def add(self, report: Report) -> None:
        await self._insert(report, self._key(str(report.id), str(report.organization_id)))

    async def save(self, report: Report) -> None:
        await self._update(
            report,
            self._key(str(report.id), str(report.organization_id)),
            pk=str(report.id),
            tenant=str(report.organization_id),
        )
