"""Exceptions for the Risks bounded context."""
from __future__ import annotations

from ..shared.exceptions import ApprovalRequired, InvalidStateTransition


class RiskNotAssessedError(InvalidStateTransition):
    pass


class RiskAcceptanceRequiresRationale(ApprovalRequired):
    pass
