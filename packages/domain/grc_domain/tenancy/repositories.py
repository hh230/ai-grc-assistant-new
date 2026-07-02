"""Repository interfaces for the Tenancy/Identity bounded context.

These are *interfaces only* — pure abstractions the domain depends on. Concrete
implementations live in the infrastructure layer, never here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import OrganizationId, UserId
from .entities import Organization, User


class OrganizationRepository(ABC):
    @abstractmethod
    async def get(self, organization_id: OrganizationId) -> Organization | None: ...

    @abstractmethod
    async def add(self, organization: Organization) -> None: ...

    @abstractmethod
    async def save(self, organization: Organization) -> None: ...


class UserRepository(ABC):
    @abstractmethod
    async def get(self, organization_id: OrganizationId, user_id: UserId) -> User | None: ...

    @abstractmethod
    async def list_for_organization(self, organization_id: OrganizationId) -> list[User]: ...

    @abstractmethod
    async def add(self, user: User) -> None: ...

    @abstractmethod
    async def save(self, user: User) -> None: ...
