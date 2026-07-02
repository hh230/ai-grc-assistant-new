"""Exceptions for the Reporting bounded context."""
from __future__ import annotations

from ..shared.exceptions import InvalidStateTransition


class IllegalReportTransition(InvalidStateTransition):
    pass
