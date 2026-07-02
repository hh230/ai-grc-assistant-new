"""Exceptions for the Policies bounded context."""
from __future__ import annotations

from ..shared.exceptions import InvalidStateTransition


class IllegalPolicyTransition(InvalidStateTransition):
    pass
