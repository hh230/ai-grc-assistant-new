"""Exceptions for the Tenancy/Identity bounded context."""
from __future__ import annotations

from ..shared.exceptions import DomainError


class UserAlreadyActiveError(DomainError):
    pass


class UserNotActiveError(DomainError):
    pass


class OrganizationNotActiveError(DomainError):
    pass
