"""Exceptions for the Workspace bounded context."""
from __future__ import annotations

from ..shared.exceptions import DomainError


class WorkspaceArchivedError(DomainError):
    """Raised when modifying an archived workspace."""
