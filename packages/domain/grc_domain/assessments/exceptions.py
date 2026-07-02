"""Exceptions for the Assessments bounded context."""
from __future__ import annotations

from ..shared.exceptions import InvalidStateTransition


class IllegalAssessmentTransition(InvalidStateTransition):
    pass
