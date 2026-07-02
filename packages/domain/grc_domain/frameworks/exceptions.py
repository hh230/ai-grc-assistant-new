"""Exceptions for the Frameworks bounded context."""
from __future__ import annotations

from ..shared.exceptions import DomainError


class FrameworkControlNotFoundError(DomainError):
    pass


class FrameworkNotPublishedError(DomainError):
    pass
