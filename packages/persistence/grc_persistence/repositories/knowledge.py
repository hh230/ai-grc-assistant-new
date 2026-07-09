"""Repository for the Knowledge (RAG source) context.

``KnowledgeSource`` follows the two-library model (CLAUDE.md's Framework Engine): a
``GLOBAL``-scoped source is visible to every tenant, an ``ORGANIZATION``-scoped source only
to its own tenant. Both read paths below return the union of "global" and "this org's own",
matching :class:`KnowledgeScope`'s two kinds.
"""

from __future__ import annotations

from grc_domain.knowledge.entities import KnowledgeSource
from grc_domain.knowledge.enums import KnowledgeScopeKind
from grc_domain.knowledge.repositories import KnowledgeSourceRepository
from grc_domain.shared.identifiers import KnowledgeSourceId, OrganizationId
from sqlalchemy import ColumnElement, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.knowledge import knowledge_source_mapper
from ..models.knowledge import KnowledgeSourceModel
from .base import SqlAlchemyAggregateRepository


def _visible_to(organization_id: OrganizationId) -> ColumnElement[bool]:
    return or_(
        KnowledgeSourceModel.scope_kind == KnowledgeScopeKind.GLOBAL.value,
        KnowledgeSourceModel.scope_organization_id == str(organization_id),
    )


def _tenant_of(source: KnowledgeSource) -> str | None:
    organization_id = source.scope.organization_id
    return str(organization_id) if organization_id is not None else None


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
            _visible_to(organization_id),
        )

    async def list_for_organization(self, organization_id: OrganizationId) -> list[KnowledgeSource]:
        return await self._list_by(
            _visible_to(organization_id),
            order_by=KnowledgeSourceModel.created_at,
        )

    async def add(self, source: KnowledgeSource) -> None:
        await self._insert(source, self._key(str(source.id), _tenant_of(source)))

    async def save(self, source: KnowledgeSource) -> None:
        tenant = _tenant_of(source)
        await self._update(
            source,
            self._key(str(source.id), tenant),
            pk=str(source.id),
            tenant=tenant,
            tenant_attr="scope_organization_id",
        )
