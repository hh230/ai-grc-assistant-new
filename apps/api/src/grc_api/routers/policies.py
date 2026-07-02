"""Policies router — the policy authoring lifecycle (CLAUDE.md §11 Policy agent domain).

Draft → submit for review → approve → publish → retire. Approval and publication are
consequential and authorized accordingly; the Application layer enforces the lifecycle rules.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from grc_domain.shared.identifiers import PolicyId
from grc_services.policies import commands as c
from grc_services.policies import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/policies", tags=["policies"])


class PolicyResponse(ApiModel):
    id: str
    organization_id: str
    title: str
    status: str
    owner_id: str
    version: int
    approved_by: str | None


class DraftPolicyRequest(ApiModel):
    title: str = Field(min_length=1)
    body_text: str = Field(min_length=1)


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Draft a policy",
    responses=problem_responses(403, 422),
)
async def draft_policy(body: DraftPolicyRequest, commands: Commands, context: Context) -> object:
    command = c.DraftPolicy(title=body.title, body_text=body.body_text)
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[PolicyResponse],
    summary="List policies",
    responses=problem_responses(403),
)
async def list_policies(queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.ListPolicies(), context))


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Get a policy",
    responses=problem_responses(403, 404),
)
async def get_policy(policy_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.GetPolicy(policy_id=PolicyId(policy_id)), context))


@router.post(
    "/{policy_id}/submit-for-review",
    response_model=PolicyResponse,
    summary="Submit a policy for review",
    responses=problem_responses(403, 404, 409),
)
async def submit_for_review(policy_id: str, commands: Commands, context: Context) -> object:
    return unwrap(
        await commands.dispatch(c.SubmitPolicyForReview(policy_id=PolicyId(policy_id)), context)
    )


@router.post(
    "/{policy_id}/approve",
    response_model=PolicyResponse,
    summary="Approve a policy (human gate)",
    responses=problem_responses(403, 404, 409),
)
async def approve_policy(policy_id: str, commands: Commands, context: Context) -> object:
    return unwrap(await commands.dispatch(c.ApprovePolicy(policy_id=PolicyId(policy_id)), context))


@router.post(
    "/{policy_id}/publish",
    response_model=PolicyResponse,
    summary="Publish a policy",
    responses=problem_responses(403, 404, 409),
)
async def publish_policy(policy_id: str, commands: Commands, context: Context) -> object:
    return unwrap(await commands.dispatch(c.PublishPolicy(policy_id=PolicyId(policy_id)), context))


@router.post(
    "/{policy_id}/retire",
    response_model=PolicyResponse,
    summary="Retire a policy",
    responses=problem_responses(403, 404, 409),
)
async def retire_policy(policy_id: str, commands: Commands, context: Context) -> object:
    return unwrap(await commands.dispatch(c.RetirePolicy(policy_id=PolicyId(policy_id)), context))
