"""Missions router — the mission lifecycle (CLAUDE.md §8), the flagship capability.

Create → plan → execute (step by step) → **human gate** (approve/reject) → complete/cancel. Each
endpoint builds a typed Command and dispatches it through the bus; the Application layer owns the
lifecycle rules, tenancy, authorization, and the human-gate invariant. The router only translates
HTTP ↔ commands and shapes the response.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from grc_domain.platform.enums import ToolSideEffect
from grc_domain.shared.identifiers import (
    AgentId,
    ApprovalGateId,
    MissionId,
    MissionStepId,
    ToolId,
    UserId,
    WorkspaceId,
)
from grc_services.missions import commands as c
from grc_services.missions import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/missions", tags=["missions"])


# ---- response models (read straight from the application DTOs) ----
class MissionStepResponse(ApiModel):
    id: str
    name: str
    status: str
    side_effect: str
    agent_id: str | None
    tool_ids: list[str]
    output_ref: str | None


class ApprovalGateResponse(ApiModel):
    id: str
    step_id: str
    decision: str
    decided_by: str | None
    proposed_action: str


class MissionResponse(ApiModel):
    id: str
    organization_id: str
    workspace_id: str
    goal: str
    status: str
    owner_id: str
    created_by: str
    steps: list[MissionStepResponse]
    approval_gates: list[ApprovalGateResponse]


class MissionSummaryResponse(ApiModel):
    id: str
    goal: str
    status: str


# ---- request models ----
class CreateMissionRequest(ApiModel):
    workspace_id: str
    goal: str = Field(min_length=1)
    owner_id: str | None = None


class PlanStepRequest(ApiModel):
    name: str = Field(min_length=1)
    side_effect: ToolSideEffect = ToolSideEffect.READ_ONLY
    agent_id: str | None = None
    tool_ids: list[str] = Field(default_factory=list)


class PlanMissionRequest(ApiModel):
    steps: list[PlanStepRequest] = Field(min_length=1)


class RequestApprovalRequest(ApiModel):
    action_description: str = Field(min_length=1)


class RejectGateRequest(ApiModel):
    reason: str = Field(min_length=1)


class CompleteStepRequest(ApiModel):
    output_ref: str | None = None


@router.post(
    "",
    response_model=MissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new mission",
    responses=problem_responses(403, 422),
)
async def create_mission(
    body: CreateMissionRequest, commands: Commands, context: Context
) -> object:
    command = c.CreateMission(
        workspace_id=WorkspaceId(body.workspace_id),
        goal=body.goal,
        owner_id=UserId(body.owner_id) if body.owner_id else None,
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[MissionSummaryResponse],
    summary="List missions in a workspace",
    responses=problem_responses(403),
)
async def list_missions(
    queries: Queries, context: Context, workspace_id: str = Query(...)
) -> object:
    query = q.ListMissionsForWorkspace(workspace_id=WorkspaceId(workspace_id))
    return unwrap(await queries.ask(query, context))


@router.get(
    "/{mission_id}",
    response_model=MissionResponse,
    summary="Get a mission",
    responses=problem_responses(403, 404),
)
async def get_mission(mission_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.GetMission(mission_id=MissionId(mission_id)), context))


@router.post(
    "/{mission_id}/plan",
    response_model=MissionResponse,
    summary="Attach an executable plan",
    responses=problem_responses(403, 404, 409, 422),
)
async def plan_mission(
    mission_id: str, body: PlanMissionRequest, commands: Commands, context: Context
) -> object:
    steps = tuple(
        c.MissionStepInput(
            name=step.name,
            side_effect=step.side_effect,
            agent_id=AgentId(step.agent_id) if step.agent_id else None,
            tool_ids=tuple(ToolId(tool_id) for tool_id in step.tool_ids),
        )
        for step in body.steps
    )
    command = c.PlanMission(mission_id=MissionId(mission_id), steps=steps)
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{mission_id}/start",
    response_model=MissionResponse,
    summary="Start executing a mission",
    responses=problem_responses(403, 404, 409),
)
async def start_mission(mission_id: str, commands: Commands, context: Context) -> object:
    command = c.StartMission(mission_id=MissionId(mission_id))
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{mission_id}/steps/{step_id}/start",
    response_model=MissionResponse,
    summary="Start a mission step",
    responses=problem_responses(403, 404, 409),
)
async def start_step(mission_id: str, step_id: str, commands: Commands, context: Context) -> object:
    command = c.StartStep(mission_id=MissionId(mission_id), step_id=MissionStepId(step_id))
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{mission_id}/steps/{step_id}/request-approval",
    response_model=MissionResponse,
    summary="Open a human-approval gate for a consequential step",
    responses=problem_responses(403, 404, 409, 422),
)
async def request_step_approval(
    mission_id: str,
    step_id: str,
    body: RequestApprovalRequest,
    commands: Commands,
    context: Context,
) -> object:
    command = c.RequestStepApproval(
        mission_id=MissionId(mission_id),
        step_id=MissionStepId(step_id),
        action_description=body.action_description,
    )
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{mission_id}/gates/{gate_id}/approve",
    response_model=MissionResponse,
    summary="Approve a human gate",
    responses=problem_responses(403, 404, 409),
)
async def approve_gate(
    mission_id: str, gate_id: str, commands: Commands, context: Context
) -> object:
    command = c.ApproveGate(mission_id=MissionId(mission_id), gate_id=ApprovalGateId(gate_id))
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{mission_id}/gates/{gate_id}/reject",
    response_model=MissionResponse,
    summary="Reject a human gate",
    responses=problem_responses(403, 404, 409, 422),
)
async def reject_gate(
    mission_id: str,
    gate_id: str,
    body: RejectGateRequest,
    commands: Commands,
    context: Context,
) -> object:
    command = c.RejectGate(
        mission_id=MissionId(mission_id), gate_id=ApprovalGateId(gate_id), reason=body.reason
    )
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{mission_id}/steps/{step_id}/complete",
    response_model=MissionResponse,
    summary="Complete a mission step",
    responses=problem_responses(403, 404, 409),
)
async def complete_step(
    mission_id: str,
    step_id: str,
    body: CompleteStepRequest,
    commands: Commands,
    context: Context,
) -> object:
    command = c.CompleteStep(
        mission_id=MissionId(mission_id),
        step_id=MissionStepId(step_id),
        output_ref=body.output_ref,
    )
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{mission_id}/complete",
    response_model=MissionResponse,
    summary="Complete a mission",
    responses=problem_responses(403, 404, 409),
)
async def complete_mission(mission_id: str, commands: Commands, context: Context) -> object:
    command = c.CompleteMission(mission_id=MissionId(mission_id))
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{mission_id}/cancel",
    response_model=MissionResponse,
    summary="Cancel a mission (fail-safe)",
    responses=problem_responses(403, 404, 409),
)
async def cancel_mission(mission_id: str, commands: Commands, context: Context) -> object:
    command = c.CancelMission(mission_id=MissionId(mission_id))
    return unwrap(await commands.dispatch(command, context))
