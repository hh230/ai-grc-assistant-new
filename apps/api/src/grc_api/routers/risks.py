"""Risks router — identification, assessment, treatment, acceptance, closure (CLAUDE.md §11)."""

from __future__ import annotations

from fastapi import APIRouter, status
from grc_domain.risks.enums import RiskImpact, RiskLikelihood, RiskTreatment
from grc_domain.shared.identifiers import RiskId
from grc_services.risks import commands as c
from grc_services.risks import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/risks", tags=["risks"])


class RiskResponse(ApiModel):
    id: str
    organization_id: str
    title: str
    status: str
    score: int | None
    level: str | None
    treatment: str | None
    accepted_by: str | None


class IdentifyRiskRequest(ApiModel):
    title: str = Field(min_length=1)
    description: str | None = None
    category: str | None = None


class AssessRiskRequest(ApiModel):
    likelihood: RiskLikelihood = Field(description="1 (rare) … 5 (almost certain)")
    impact: RiskImpact = Field(description="1 (negligible) … 5 (severe)")


class TreatmentRequest(ApiModel):
    treatment: RiskTreatment


class AcceptRiskRequest(ApiModel):
    rationale: str = Field(min_length=1)


@router.post(
    "",
    response_model=RiskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Identify a risk",
    responses=problem_responses(403, 422),
)
async def identify_risk(body: IdentifyRiskRequest, commands: Commands, context: Context) -> object:
    command = c.IdentifyRisk(title=body.title, description=body.description, category=body.category)
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[RiskResponse],
    summary="List risks",
    responses=problem_responses(403),
)
async def list_risks(queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.ListRisks(), context))


@router.get(
    "/{risk_id}",
    response_model=RiskResponse,
    summary="Get a risk",
    responses=problem_responses(403, 404),
)
async def get_risk(risk_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.GetRisk(risk_id=RiskId(risk_id)), context))


@router.post(
    "/{risk_id}/assessment",
    response_model=RiskResponse,
    summary="Assess a risk (likelihood × impact)",
    responses=problem_responses(403, 404, 409, 422),
)
async def assess_risk(
    risk_id: str, body: AssessRiskRequest, commands: Commands, context: Context
) -> object:
    command = c.AssessRisk(risk_id=RiskId(risk_id), likelihood=body.likelihood, impact=body.impact)
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{risk_id}/treatment",
    response_model=RiskResponse,
    summary="Plan a risk treatment",
    responses=problem_responses(403, 404, 409, 422),
)
async def plan_treatment(
    risk_id: str, body: TreatmentRequest, commands: Commands, context: Context
) -> object:
    command = c.PlanRiskTreatment(risk_id=RiskId(risk_id), treatment=body.treatment)
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{risk_id}/acceptance",
    response_model=RiskResponse,
    summary="Accept a risk (human decision)",
    responses=problem_responses(403, 404, 409, 422),
)
async def accept_risk(
    risk_id: str, body: AcceptRiskRequest, commands: Commands, context: Context
) -> object:
    command = c.AcceptRisk(risk_id=RiskId(risk_id), rationale=body.rationale)
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{risk_id}/close",
    response_model=RiskResponse,
    summary="Close a risk",
    responses=problem_responses(403, 404, 409),
)
async def close_risk(risk_id: str, commands: Commands, context: Context) -> object:
    return unwrap(await commands.dispatch(c.CloseRisk(risk_id=RiskId(risk_id)), context))
