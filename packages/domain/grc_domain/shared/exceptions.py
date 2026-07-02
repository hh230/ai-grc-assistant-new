"""Shared domain exceptions (base hierarchy)."""
from __future__ import annotations


class DomainError(Exception):
    """Base class for every domain error. Carries a human-readable message only."""


class InvariantViolation(DomainError):
    """Raised when an operation would violate an aggregate invariant."""


class InvalidStateTransition(DomainError):
    """Raised when an entity is moved through an illegal lifecycle transition."""


class ApprovalRequired(DomainError):
    """Raised when a consequential action is attempted without a granted human gate."""


class TenantIsolationError(DomainError):
    """Raised when an operation would cross tenant boundaries."""


class NotFoundError(DomainError):
    """Raised by domain services when a referenced aggregate does not exist."""
