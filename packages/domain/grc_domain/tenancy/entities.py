"""Entities and aggregate roots for the Tenancy/Identity bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.entity import AggregateRoot
from ..shared.identifiers import OrganizationId, UserId
from .enums import OrganizationStatus, UserRole, UserStatus
from .events import (
    OrganizationRegistered,
    OrganizationSuspended,
    UserActivated,
    UserDeactivated,
    UserInvited,
    UserRoleGranted,
)
from .exceptions import (
    OrganizationNotActiveError,
    UserAlreadyActiveError,
    UserNotActiveError,
)
from .value_objects import Email, Region

# Roles permitted to approve consequential GRC actions (human gates).
_APPROVER_ROLES: frozenset[UserRole] = frozenset(
    {UserRole.OWNER, UserRole.ADMIN, UserRole.COMPLIANCE_MANAGER, UserRole.RISK_MANAGER}
)


@dataclass(kw_only=True, eq=False)
class Organization(AggregateRoot):
    """A tenant. The root of tenant isolation across the platform."""

    id: OrganizationId
    name: str
    region: Region
    status: OrganizationStatus = OrganizationStatus.ACTIVE

    @classmethod
    def register(cls, *, id: OrganizationId, name: str, region: Region) -> Organization:
        if not name.strip():
            raise ValueError("Organization name must not be empty")
        org = cls(id=id, name=name, region=region)
        org._record_event(OrganizationRegistered(organization_id=id, name=name))
        return org

    @property
    def is_active(self) -> bool:
        return self.status is OrganizationStatus.ACTIVE

    def suspend(self, *, reason: str | None = None) -> None:
        if self.status is OrganizationStatus.CLOSED:
            raise OrganizationNotActiveError("Closed organizations cannot be suspended")
        self.status = OrganizationStatus.SUSPENDED
        self._record_event(OrganizationSuspended(organization_id=self.id, reason=reason))


@dataclass(kw_only=True, eq=False)
class User(AggregateRoot):
    """A member of an organization. Tenant-bound by `organization_id`."""

    id: UserId
    organization_id: OrganizationId
    email: Email
    display_name: str
    status: UserStatus = UserStatus.INVITED
    roles: set[UserRole] = field(default_factory=set)

    @classmethod
    def invite(
        cls,
        *,
        id: UserId,
        organization_id: OrganizationId,
        email: Email,
        display_name: str,
        roles: set[UserRole] | None = None,
    ) -> User:
        user = cls(
            id=id,
            organization_id=organization_id,
            email=email,
            display_name=display_name,
            roles=set(roles or set()),
        )
        user._record_event(UserInvited(organization_id=organization_id, user_id=id))
        return user

    def activate(self) -> None:
        if self.status is UserStatus.ACTIVE:
            raise UserAlreadyActiveError("User is already active")
        self.status = UserStatus.ACTIVE
        self._record_event(UserActivated(organization_id=self.organization_id, user_id=self.id))

    def deactivate(self) -> None:
        if self.status is not UserStatus.ACTIVE:
            raise UserNotActiveError("Only active users can be deactivated")
        self.status = UserStatus.DEACTIVATED
        self._record_event(UserDeactivated(organization_id=self.organization_id, user_id=self.id))

    def grant_role(self, role: UserRole) -> None:
        if role not in self.roles:
            self.roles.add(role)
            self._touch()
            self._record_event(
                UserRoleGranted(organization_id=self.organization_id, user_id=self.id, role=role)
            )

    @property
    def can_approve(self) -> bool:
        """Whether this user may satisfy a human approval gate."""
        return self.status is UserStatus.ACTIVE and bool(self.roles & _APPROVER_ROLES)
