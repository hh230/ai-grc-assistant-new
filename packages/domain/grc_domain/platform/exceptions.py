"""Exceptions for the Platform bounded context."""
from __future__ import annotations

from ..shared.exceptions import DomainError, InvariantViolation


class ToolNotAvailableError(DomainError):
    pass


class AgentToolNotGrantedError(InvariantViolation):
    """An agent may only use tools it has been explicitly granted (least privilege)."""
