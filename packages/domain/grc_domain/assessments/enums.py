"""Enumerations for the Assessments bounded context."""
from __future__ import annotations

from enum import Enum


class AssessmentType(str, Enum):
    GAP_ANALYSIS = "gap_analysis"
    READINESS = "readiness"
    CONTROL_TEST = "control_test"


class AssessmentStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CoverageLevel(str, Enum):
    NOT_COVERED = "not_covered"
    PARTIALLY_COVERED = "partially_covered"
    COVERED = "covered"
    NOT_APPLICABLE = "not_applicable"
