"""Repository for the Evidence context."""

from __future__ import annotations

from grc_domain.evidence.entities import Evidence
from grc_domain.evidence.repositories import EvidenceRepository
from grc_domain.shared.identifiers import ControlId, EvidenceId, OrganizationId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.evidence import evidence_mapper
from ..models.evidence import EvidenceModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyEvidenceRepository(
    SqlAlchemyAggregateRepository[Evidence, EvidenceModel], EvidenceRepository
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, evidence_mapper, tracker, cache, EvidenceModel)

    async def get(
        self, organization_id: OrganizationId, evidence_id: EvidenceId
    ) -> Evidence | None:
        return await self._get_by(
            self._key(str(evidence_id), str(organization_id)),
            EvidenceModel.id == str(evidence_id),
            EvidenceModel.organization_id == str(organization_id),
        )

    async def list_for_control(
        self, organization_id: OrganizationId, control_id: ControlId
    ) -> list[Evidence]:
        # Control linkage is stored as a JSON id set on each evidence row. We scope by
        # tenant in SQL and filter the membership in memory to stay portable across
        # dialects; a JSONB GIN index (or a link table) is the future optimization.
        rows = await self._fetch_all(
            EvidenceModel.organization_id == str(organization_id),
            order_by=EvidenceModel.created_at,
        )
        target = str(control_id)
        return [self._materialize(row) for row in rows if target in (row.linked_control_ids or [])]

    async def add(self, evidence: Evidence) -> None:
        await self._insert(evidence, self._key(str(evidence.id), str(evidence.organization_id)))

    async def save(self, evidence: Evidence) -> None:
        await self._update(
            evidence,
            self._key(str(evidence.id), str(evidence.organization_id)),
            pk=str(evidence.id),
            tenant=str(evidence.organization_id),
        )
