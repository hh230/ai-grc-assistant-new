"""Frameworks router — compliance standards as data (CLAUDE.md §13, ADR-0007).

Frameworks are global catalog data (not tenant-scoped). Import/publish/deprecate are platform-
admin operations; reads are available to any authenticated principal with catalog read access.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from grc_domain.frameworks.value_objects import FrameworkControl, Requirement
from grc_domain.shared.identifiers import FrameworkControlId, FrameworkId
from grc_services.frameworks import commands as c
from grc_services.frameworks import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


class FrameworkResponse(ApiModel):
    id: str
    name: str
    version: str
    status: str
    region: str | None
    languages: list[str]
    control_count: int


class RequirementRequest(ApiModel):
    code: str = Field(min_length=1)
    text: str = Field(min_length=1)


class FrameworkControlRequest(ApiModel):
    id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    requirements: list[RequirementRequest] = Field(default_factory=list)


class ImportFrameworkRequest(ApiModel):
    framework_id: str = Field(min_length=1, examples=["framework:iso_27001"])
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    region: str | None = None
    languages: list[str] = Field(default_factory=list)
    controls: list[FrameworkControlRequest] = Field(default_factory=list)


class FrameworkVersionRequest(ApiModel):
    version: str = Field(min_length=1)


@router.post(
    "",
    response_model=FrameworkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a framework definition",
    responses=problem_responses(403, 409, 422),
)
async def import_framework(
    body: ImportFrameworkRequest, commands: Commands, context: Context
) -> object:
    controls = tuple(
        FrameworkControl(
            id=FrameworkControlId(control.id),
            code=control.code,
            title=control.title,
            domain=control.domain,
            requirements=tuple(
                Requirement(code=req.code, text=req.text) for req in control.requirements
            ),
        )
        for control in body.controls
    )
    command = c.ImportFramework(
        framework_id=FrameworkId(body.framework_id),
        name=body.name,
        version=body.version,
        controls=controls,
        region=body.region,
        languages=tuple(body.languages),
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[FrameworkResponse],
    summary="List published frameworks",
    responses=problem_responses(403),
)
async def list_frameworks(queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.ListPublishedFrameworks(), context))


@router.get(
    "/{framework_id}",
    response_model=FrameworkResponse,
    summary="Get a framework version",
    responses=problem_responses(403, 404),
)
async def get_framework(
    framework_id: str, queries: Queries, context: Context, version: str = Query(...)
) -> object:
    query = q.GetFramework(framework_id=FrameworkId(framework_id), version=version)
    return unwrap(await queries.ask(query, context))


@router.post(
    "/{framework_id}/publish",
    response_model=FrameworkResponse,
    summary="Publish a framework version",
    responses=problem_responses(403, 404, 409),
)
async def publish_framework(
    framework_id: str, body: FrameworkVersionRequest, commands: Commands, context: Context
) -> object:
    command = c.PublishFramework(framework_id=FrameworkId(framework_id), version=body.version)
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{framework_id}/deprecate",
    response_model=FrameworkResponse,
    summary="Deprecate a framework version",
    responses=problem_responses(403, 404, 409),
)
async def deprecate_framework(
    framework_id: str, body: FrameworkVersionRequest, commands: Commands, context: Context
) -> object:
    command = c.DeprecateFramework(framework_id=FrameworkId(framework_id), version=body.version)
    return unwrap(await commands.dispatch(command, context))
