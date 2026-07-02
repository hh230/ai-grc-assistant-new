"""Application-layer exceptions.

These are *application* concerns (authorization, validation, not-found, conflict), distinct
from domain errors (`grc_domain.shared.exceptions.DomainError`). Handlers translate domain
errors into these where appropriate at the boundary.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Base class for all application-layer errors."""

    code: str = "application_error"


class AuthorizationError(ApplicationError):
    """Raised when the current principal is not allowed to perform an action."""

    code = "authorization_error"


class ValidationError(ApplicationError):
    """Raised when a command/query fails input validation."""

    code = "validation_error"

    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or [message]


class ResourceNotFoundError(ApplicationError):
    """Raised when a referenced aggregate does not exist (within the tenant)."""

    code = "not_found"


class ConflictError(ApplicationError):
    """Raised when an operation conflicts with current state."""

    code = "conflict"


class ConcurrencyError(ConflictError):
    """Raised when an optimistic-concurrency check fails."""

    code = "concurrency_conflict"


class UnitOfWorkError(ApplicationError):
    """Raised when a unit of work cannot be committed."""

    code = "unit_of_work_error"
