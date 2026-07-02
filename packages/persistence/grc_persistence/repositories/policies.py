"""Repository for the Policies context."""

from __future__ import annotations

from grc_domain.policies.entities import Policy
from grc_domain.policies.repositories import PolicyRepository
from grc_domain.shared.identifiers import OrganizationId, PolicyId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.policies import policy_mapper
from ..models.policies import PolicyModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyPolicyRepository(
    SqlAlchemyAggregateRepository[Policy, PolicyModel], PolicyRepository
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, policy_mapper, tracker, cache, PolicyModel)

    async def get(self, organization_id: OrganizationId, policy_id: PolicyId) -> Policy | None:
        return await self._get_by(
            self._key(str(policy_id), str(organization_id)),
            PolicyModel.id == str(policy_id),
            PolicyModel.organization_id == str(organization_id),
        )

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Policy]:
        return await self._list_by(
            PolicyModel.organization_id == str(organization_id),
            order_by=PolicyModel.created_at,
        )

    async def add(self, policy: Policy) -> None:
        await self._insert(policy, self._key(str(policy.id), str(policy.organization_id)))

    async def save(self, policy: Policy) -> None:
        await self._update(
            policy,
            self._key(str(policy.id), str(policy.organization_id)),
            pk=str(policy.id),
            tenant=str(policy.organization_id),
        )
