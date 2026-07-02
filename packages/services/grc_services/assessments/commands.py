"""Commands for the Assessment capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.assessments.enums import AssessmentType, CoverageLevel
from grc_domain.shared.identifiers import (
    AssessmentId,
    ControlId,
    FrameworkControlId,
    FrameworkId,
    WorkspaceId,
)

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class PlanAssessment(Command):
    workspace_id: WorkspaceId
    framework_id: FrameworkId
    framework_version: str
    assessment_type: AssessmentType = AssessmentType.GAP_ANALYSIS


@dataclass(frozen=True, kw_only=True)
class StartAssessment(Command):
    assessment_id: AssessmentId


@dataclass(frozen=True, kw_only=True)
class RecordAssessmentResult(Command):
    assessment_id: AssessmentId
    framework_control_id: FrameworkControlId
    coverage: CoverageLevel
    satisfied_by_control_id: ControlId | None = None
    notes: str | None = None


@dataclass(frozen=True, kw_only=True)
class CompleteAssessment(Command):
    assessment_id: AssessmentId
