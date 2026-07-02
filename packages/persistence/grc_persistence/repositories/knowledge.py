"""Repository for the Knowledge (RAG source) context."""

from __future__ import annotations

from grc_domain.knowledge.entities import KnowledgeSource
from grc_domain.knowledge.repositories import KnowledgeSourceRepository
from grc_domain.shared.identifiers import KnowledgeSourceId, OrganizationId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.knowledge import knowledge_source_mapper
from ..models.knowledge import KnowledgeSourceModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyKnowledgeSourceRepository(
    SqlAlchemyAggregateRepository[KnowledgeSource, KnowledgeSourceModel],
    KnowledgeSourceRepository,
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, knowledge_source_mapper, tracker, cache, KnowledgeSourceModel)

    async def get(
        self, organization_id: OrganizationId, source_id: KnowledgeSourceId
    ) -> KnowledgeSource | None:
        return await self._get_by(
            self._key(str(source_id), str(organization_id)),
            KnowledgeSourceModel.id == str(source_id),
            KnowledgeSourceModel.organization_id == str(organization_id),
        )

    async def list_for_organization(self, organization_id: OrganizationId) -> list[KnowledgeSource]:
        return await self._list_by(
            KnowledgeSourceModel.organization_id == str(organization_id),
            order_by=KnowledgeSourceModel.created_at,
        )

    async def add(self, source: KnowledgeSource) -> None:
        await self._insert(source, self._key(str(source.id), str(source.organization_id)))

    async def save(self, source: KnowledgeSource) -> None:
        await self._update(
            source,
            self._key(str(source.id), str(source.organization_id)),
            pk=str(source.id),
            tenant=str(source.organization_id),
        )
