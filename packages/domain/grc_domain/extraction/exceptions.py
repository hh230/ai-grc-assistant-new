"""Exceptions for the Knowledge Extraction bounded context."""
from __future__ import annotations

from ..shared.exceptions import InvalidStateTransition, NotFoundError


class IllegalExtractionRunTransition(InvalidStateTransition):
    """Raised when an extraction run is moved through an illegal lifecycle transition."""


class IllegalStageTransition(InvalidStateTransition):
    """Raised when a stage is started/finished while the run is not in a valid state."""


class StageExecutionNotFound(NotFoundError):
    """Raised when no running execution exists for a stage being completed/failed."""
