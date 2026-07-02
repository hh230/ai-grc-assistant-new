"""Exceptions for the Evidence bounded context."""
from __future__ import annotations

from ..shared.exceptions import InvalidStateTransition


class IllegalEvidenceTransition(InvalidStateTransition):
    pass
