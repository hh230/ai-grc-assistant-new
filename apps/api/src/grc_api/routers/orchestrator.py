"""Orchestrator router — the governed AI entry point (CLAUDE.md §7).

A caller submits a *goal*; the Orchestrator (the brain) deterministically routes it to a
specialized agent, runs it, and returns the **decision trail**, the agent's grounded proposal,
and whether the output is **held for human approval**. Consequential output is never auto-applied
here — the orchestrator only proposes (CLAUDE.md §7, §11). The endpoint is authorized (execute a
mission) and exposes sources/confidence/decisions for transparency, never raw chain-of-thought
(§19).
"""

from __future__ import annotations

from fastapi import APIRouter, status
from grc_agents.exceptions import AgentError, NoAgentForRoleError
from grc_agents.tasks import AgentRole
from grc_services.shared.authorization import Action, ResourceType
from grc_services.shared.exceptions import ValidationError as AppValidationError
from pydantic import BaseModel, ConfigDict, Field

from ..schemas.common import ProblemDetail, problem_responses
from ..security.dependencies import Authz, Context, OrchestratorDep

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


class OrchestratorRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=1, examples=["Perform a control gap analysis for ISO 27001"])
    role: AgentRole | None = Field(
        default=None,
        description="Force a specific agent role; omit to let the orchestrator route the goal.",
    )


class DecisionStep(BaseModel):
    step: str
    agent: str
    detail: str


class AgentResultResponse(BaseModel):
    agent: str
    role: str
    output: str
    confidence: float
    requires_human_approval: bool
    citations: list[str]
    model: str | None


class OrchestratorRunResponse(BaseModel):
    goal: str
    route: str
    awaiting_approval: bool
    decisions: list[DecisionStep]
    result: AgentResultResponse


@router.post(
    "/runs",
    response_model=OrchestratorRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run a goal through the AI Orchestrator",
    responses=problem_responses(403, 422),
)
async def run_goal(
    body: OrchestratorRunRequest,
    orchestrator: OrchestratorDep,
    authz: Authz,
    context: Context,
) -> OrchestratorRunResponse:
    # Governed: running the orchestrator is executing mission work, and is authorized as such.
    await authz.ensure_can(context, Action.EXECUTE, ResourceType.MISSION)
    try:
        outcome = await orchestrator.run(body.goal, role=body.role)
    except NoAgentForRoleError as error:
        raise AppValidationError(str(error)) from error
    except (AgentError, ValueError) as error:
        raise AppValidationError(str(error)) from error

    return OrchestratorRunResponse(
        goal=outcome.goal,
        route=outcome.route.value,
        awaiting_approval=outcome.awaiting_approval,
        decisions=[
            DecisionStep(step=d.step, agent=d.agent, detail=d.detail) for d in outcome.decisions
        ],
        result=AgentResultResponse(
            agent=outcome.result.agent,
            role=outcome.result.role.value,
            output=outcome.result.output,
            confidence=outcome.result.confidence,
            requires_human_approval=outcome.result.requires_human_approval,
            citations=list(outcome.result.citations),
            model=outcome.result.model,
        ),
    )


# Re-exported so the OpenAPI schema documents the problem shape for this router too.
__all__ = ["router", "ProblemDetail"]
