"""Domain events for the Assessments bounded context."""
from __future__ import annotations

from dataclasses import dataclass

from ..shared.events import DomainEvent
from ..shared.identifiers import AssessmentId, FrameworkControlId, FrameworkId, OrganizationId
from .value_objects import CoverageSummary


@dataclass(frozen=True, kw_only=True)
class AssessmentStarted(DomainEvent):
    assessment_id: AssessmentId
    organization_id: OrganizationId
    framework_id: FrameworkId


@dataclass(frozen=True, kw_only=True)
class ControlAssessed(DomainEvent):
    assessment_id: AssessmentId
    framework_control_id: FrameworkControlId


@dataclass(frozen=True, kw_only=True)
class AssessmentCompleted(DomainEvent):
    assessment_id: AssessmentId
    summary: CoverageSummary
