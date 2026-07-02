"""Assessments router — framework assessments and coverage results (CLAUDE.md §11 Compliance)."""

from __future__ import annotations

from fastapi import APIRouter, status
from grc_domain.assessments.enums import AssessmentType, CoverageLevel
from grc_domain.shared.identifiers import (
    AssessmentId,
    ControlId,
    FrameworkControlId,
    FrameworkId,
    WorkspaceId,
)
from grc_services.assessments import commands as c
from grc_services.assessments import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/assessments", tags=["assessments"])


class CoverageSummaryResponse(ApiModel):
    total: int
    covered: int
    partially_covered: int
    not_covered: int
    not_applicable: int
    coverage_ratio: float


class AssessmentResponse(ApiModel):
    id: str
    organization_id: str
    workspace_id: str
    framework_id: str
    framework_version: str
    assessment_type: str
    status: str
    result_count: int
    summary: CoverageSummaryResponse | None


class PlanAssessmentRequest(ApiModel):
    workspace_id: str = Field(min_length=1)
    framework_id: str = Field(min_length=1)
    framework_version: str = Field(min_length=1)
    assessment_type: AssessmentType = AssessmentType.GAP_ANALYSIS


class RecordResultRequest(ApiModel):
    framework_control_id: str = Field(min_length=1)
    coverage: CoverageLevel
    satisfied_by_control_id: str | None = None
    notes: str | None = None


@router.post(
    "",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Plan an assessment",
    responses=problem_responses(403, 422),
)
async def plan_assessment(
    body: PlanAssessmentRequest, commands: Commands, context: Context
) -> object:
    command = c.PlanAssessment(
        workspace_id=WorkspaceId(body.workspace_id),
        framework_id=FrameworkId(body.framework_id),
        framework_version=body.framework_version,
        assessment_type=body.assessment_type,
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[AssessmentResponse],
    summary="List assessments",
    responses=problem_responses(403),
)
async def list_assessments(queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.ListAssessments(), context))


@router.get(
    "/{assessment_id}",
    response_model=AssessmentResponse,
    summary="Get an assessment",
    responses=problem_responses(403, 404),
)
async def get_assessment(assessment_id: str, queries: Queries, context: Context) -> object:
    query = q.GetAssessment(assessment_id=AssessmentId(assessment_id))
    return unwrap(await queries.ask(query, context))


@router.post(
    "/{assessment_id}/start",
    response_model=AssessmentResponse,
    summary="Start an assessment",
    responses=problem_responses(403, 404, 409),
)
async def start_assessment(assessment_id: str, commands: Commands, context: Context) -> object:
    command = c.StartAssessment(assessment_id=AssessmentId(assessment_id))
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{assessment_id}/results",
    response_model=AssessmentResponse,
    summary="Record a per-control coverage result",
    responses=problem_responses(403, 404, 409, 422),
)
async def record_result(
    assessment_id: str, body: RecordResultRequest, commands: Commands, context: Context
) -> object:
    command = c.RecordAssessmentResult(
        assessment_id=AssessmentId(assessment_id),
        framework_control_id=FrameworkControlId(body.framework_control_id),
        coverage=body.coverage,
        satisfied_by_control_id=(
            ControlId(body.satisfied_by_control_id) if body.satisfied_by_control_id else None
        ),
        notes=body.notes,
    )
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{assessment_id}/complete",
    response_model=AssessmentResponse,
    summary="Complete an assessment",
    responses=problem_responses(403, 404, 409),
)
async def complete_assessment(assessment_id: str, commands: Commands, context: Context) -> object:
    command = c.CompleteAssessment(assessment_id=AssessmentId(assessment_id))
    return unwrap(await commands.dispatch(command, context))
