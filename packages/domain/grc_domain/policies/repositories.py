"""Repository interface for the Policies bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import OrganizationId, PolicyId
from .entities import Policy


class PolicyRepository(ABC):
    @abstractmethod
    async def get(self, organization_id: OrganizationId, policy_id: PolicyId) -> Policy | None: ...

    @abstractmethod
    async def list_for_organization(self, organization_id: OrganizationId) -> list[Policy]: ...

    @abstractmethod
    async def add(self, policy: Policy) -> None: ...

    @abstractmethod
    async def save(self, policy: Policy) -> None: ...
