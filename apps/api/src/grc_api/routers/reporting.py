"""Reporting router — audit-ready deliverables (CLAUDE.md §11 Report agent domain)."""

from __future__ import annotations

from fastapi import APIRouter, status
from grc_domain.reporting.enums import ReportType
from grc_domain.reporting.value_objects import ReportSection
from grc_domain.shared.identifiers import AssessmentId, MissionId, ReportId
from grc_services.reporting import commands as c
from grc_services.reporting import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/reports", tags=["reporting"])


class ReportResponse(ApiModel):
    id: str
    organization_id: str
    report_type: str
    title: str
    status: str
    section_count: int


class RequestReportRequest(ApiModel):
    report_type: ReportType
    title: str = Field(min_length=1)
    source_mission_id: str | None = None
    source_assessment_id: str | None = None


class ReportSectionRequest(ApiModel):
    heading: str = Field(min_length=1)
    body: str


class AttachContentRequest(ApiModel):
    sections: list[ReportSectionRequest] = Field(min_length=1)


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request a report",
    responses=problem_responses(403, 422),
)
async def request_report(
    body: RequestReportRequest, commands: Commands, context: Context
) -> object:
    command = c.RequestReport(
        report_type=body.report_type,
        title=body.title,
        source_mission_id=MissionId(body.source_mission_id) if body.source_mission_id else None,
        source_assessment_id=(
            AssessmentId(body.source_assessment_id) if body.source_assessment_id else None
        ),
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[ReportResponse],
    summary="List reports",
    responses=problem_responses(403),
)
async def list_reports(queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.ListReports(), context))


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get a report",
    responses=problem_responses(403, 404),
)
async def get_report(report_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.GetReport(report_id=ReportId(report_id)), context))


@router.post(
    "/{report_id}/content",
    response_model=ReportResponse,
    summary="Attach report content (sections)",
    responses=problem_responses(403, 404, 409, 422),
)
async def attach_content(
    report_id: str, body: AttachContentRequest, commands: Commands, context: Context
) -> object:
    sections = tuple(
        ReportSection(heading=section.heading, body=section.body) for section in body.sections
    )
    command = c.AttachReportContent(report_id=ReportId(report_id), sections=sections)
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{report_id}/finalize",
    response_model=ReportResponse,
    summary="Finalize a report",
    responses=problem_responses(403, 404, 409),
)
async def finalize_report(report_id: str, commands: Commands, context: Context) -> object:
    return unwrap(await commands.dispatch(c.FinalizeReport(report_id=ReportId(report_id)), context))


@router.post(
    "/{report_id}/publish",
    response_model=ReportResponse,
    summary="Publish a report",
    responses=problem_responses(403, 404, 409),
)
async def publish_report(report_id: str, commands: Commands, context: Context) -> object:
    return unwrap(await commands.dispatch(c.PublishReport(report_id=ReportId(report_id)), context))
