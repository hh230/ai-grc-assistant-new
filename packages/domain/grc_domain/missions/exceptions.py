"""Exceptions for the Missions bounded context."""
from __future__ import annotations

from ..shared.exceptions import ApprovalRequired, DomainError, InvalidStateTransition


class IllegalMissionTransition(InvalidStateTransition):
    """Raised on an illegal mission lifecycle transition."""


class MissionStepNotFound(DomainError):
    pass


class ConsequentialStepNeedsApproval(ApprovalRequired):
    """A consequential step cannot complete without a granted approval gate."""
