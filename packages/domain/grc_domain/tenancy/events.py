"""Domain events for the Tenancy/Identity bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import OrganizationId, UserId
from .enums import UserRole


@dataclass(frozen=True, kw_only=True)
class OrganizationRegistered(DomainEvent):
    organization_id: OrganizationId
    name: str


@dataclass(frozen=True, kw_only=True)
class OrganizationSuspended(DomainEvent):
    organization_id: OrganizationId
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class UserInvited(DomainEvent):
    organization_id: OrganizationId
    user_id: UserId


@dataclass(frozen=True, kw_only=True)
class UserActivated(DomainEvent):
    organization_id: OrganizationId
    user_id: UserId


@dataclass(frozen=True, kw_only=True)
class UserDeactivated(DomainEvent):
    organization_id: OrganizationId
    user_id: UserId


@dataclass(frozen=True, kw_only=True)
class UserRoleGranted(DomainEvent):
    organization_id: OrganizationId
    user_id: UserId
    role: UserRole
