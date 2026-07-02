"""Repositories for the Tenancy/Identity context."""

from __future__ import annotations

from grc_domain.shared.identifiers import OrganizationId, UserId
from grc_domain.tenancy.entities import Organization, User
from grc_domain.tenancy.repositories import OrganizationRepository, UserRepository
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.tenancy import organization_mapper, user_mapper
from ..models.tenancy import OrganizationModel, UserModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyOrganizationRepository(
    SqlAlchemyAggregateRepository[Organization, OrganizationModel], OrganizationRepository
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, organization_mapper, tracker, cache, OrganizationModel)

    async def get(self, organization_id: OrganizationId) -> Organization | None:
        return await self._get_by(
            self._key(str(organization_id)),
            OrganizationModel.id == str(organization_id),
        )

    async def add(self, organization: Organization) -> None:
        await self._insert(organization, self._key(str(organization.id)))

    async def save(self, organization: Organization) -> None:
        await self._update(organization, self._key(str(organization.id)), pk=str(organization.id))


class SqlAlchemyUserRepository(SqlAlchemyAggregateRepository[User, UserModel], UserRepository):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, user_mapper, tracker, cache, UserModel)

    async def get(self, organization_id: OrganizationId, user_id: UserId) -> User | None:
        return await self._get_by(
            self._key(str(user_id), str(organization_id)),
            UserModel.id == str(user_id),
            UserModel.organization_id == str(organization_id),
        )

    async def list_for_organization(self, organization_id: OrganizationId) -> list[User]:
        return await self._list_by(
            UserModel.organization_id == str(organization_id),
            order_by=UserModel.created_at,
        )

    async def add(self, user: User) -> None:
        await self._insert(user, self._key(str(user.id), str(user.organization_id)))

    async def save(self, user: User) -> None:
        await self._update(
            user,
            self._key(str(user.id), str(user.organization_id)),
            pk=str(user.id),
            tenant=str(user.organization_id),
        )
