"""Repository for the Risks context."""

from __future__ import annotations

from grc_domain.risks.entities import Risk
from grc_domain.risks.repositories import RiskRepository
from grc_domain.shared.identifiers import OrganizationId, RiskId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.risks import risk_mapper
from ..models.risks import RiskModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyRiskRepository(SqlAlchemyAggregateRepository[Risk, RiskModel], RiskRepository):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, risk_mapper, tracker, cache, RiskModel)

    async def get(self, organization_id: OrganizationId, risk_id: RiskId) -> Risk | None:
        return await self._get_by(
            self._key(str(risk_id), str(organization_id)),
            RiskModel.id == str(risk_id),
            RiskModel.organization_id == str(organization_id),
        )

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Risk]:
        return await self._list_by(
            RiskModel.organization_id == str(organization_id),
            order_by=RiskModel.created_at,
        )

    async def add(self, risk: Risk) -> None:
        await self._insert(risk, self._key(str(risk.id), str(risk.organization_id)))

    async def save(self, risk: Risk) -> None:
        await self._update(
            risk,
            self._key(str(risk.id), str(risk.organization_id)),
            pk=str(risk.id),
            tenant=str(risk.organization_id),
        )
