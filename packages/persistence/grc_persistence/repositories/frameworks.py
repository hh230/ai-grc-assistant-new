"""Repositories for the Frameworks context."""

from __future__ import annotations

from grc_domain.frameworks.entities import Framework, FrameworkMappingSet
from grc_domain.frameworks.enums import FrameworkStatus
from grc_domain.frameworks.repositories import (
    FrameworkMappingRepository,
    FrameworkRepository,
)
from grc_domain.frameworks.value_objects import FrameworkVersion
from grc_domain.shared.identifiers import FrameworkId, FrameworkMappingId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.frameworks import framework_mapper, framework_mapping_set_mapper
from ..models.frameworks import FrameworkMappingSetModel, FrameworkModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyFrameworkRepository(
    SqlAlchemyAggregateRepository[Framework, FrameworkModel], FrameworkRepository
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, framework_mapper, tracker, cache, FrameworkModel)

    @staticmethod
    def _identity(framework_id: FrameworkId, version: FrameworkVersion) -> str:
        return f"{framework_id}@{version}"

    async def get(self, framework_id: FrameworkId, version: FrameworkVersion) -> Framework | None:
        return await self._get_by(
            self._key(self._identity(framework_id, version)),
            FrameworkModel.id == str(framework_id),
            FrameworkModel.version_label == str(version),
        )

    async def list_published(self) -> list[Framework]:
        return await self._list_by(
            FrameworkModel.status == FrameworkStatus.PUBLISHED.value,
            order_by=FrameworkModel.id,
        )

    async def add(self, framework: Framework) -> None:
        await self._insert(framework, self._key(self._identity(framework.id, framework.version)))

    async def save(self, framework: Framework) -> None:
        await self._update(
            framework,
            self._key(self._identity(framework.id, framework.version)),
            pk=(str(framework.id), str(framework.version)),
        )


class SqlAlchemyFrameworkMappingRepository(
    SqlAlchemyAggregateRepository[FrameworkMappingSet, FrameworkMappingSetModel],
    FrameworkMappingRepository,
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(
            session, framework_mapping_set_mapper, tracker, cache, FrameworkMappingSetModel
        )

    async def get(self, mapping_id: FrameworkMappingId) -> FrameworkMappingSet | None:
        return await self._get_by(
            self._key(str(mapping_id)),
            FrameworkMappingSetModel.id == str(mapping_id),
        )

    async def find_between(
        self, source_framework_id: FrameworkId, target_framework_id: FrameworkId
    ) -> FrameworkMappingSet | None:
        rows = await self._fetch_all(
            FrameworkMappingSetModel.source_framework_id == str(source_framework_id),
            FrameworkMappingSetModel.target_framework_id == str(target_framework_id),
            order_by=FrameworkMappingSetModel.created_at,
        )
        return self._materialize(rows[0]) if rows else None

    async def add(self, mapping_set: FrameworkMappingSet) -> None:
        await self._insert(mapping_set, self._key(str(mapping_set.id)))
