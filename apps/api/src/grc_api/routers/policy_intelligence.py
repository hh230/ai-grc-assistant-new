"""Policy Intelligence router — Policy Hunter (PI-P3) and Policy Analyst (PI-P4) exposed over
HTTP (PI-P5, ADR-0022). Both agents are read-only reporting capabilities: they never draft,
edit, or approve a policy, so there is nothing here for a human gate to hold (CLAUDE.md §9's
gate applies to *consequential* Tools; both of these are ``ToolSideEffect.READ_ONLY``).

Every call goes through the same path a Tool must always go through (CLAUDE.md §9-10): the
Tool Registry validates input, checks the tool's declared permission, executes, and
unconditionally audits — success, denial, or failure alike (CLAUDE.md §19). This router's own
job is thin: authorize the HTTP caller to read Policy data at all (the same RBAC gate
``/policies`` already enforces), translate that into the Tool Registry's caller context, and
shape the response.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from grc_policy_analyst.exceptions import PolicyNotFoundError
from grc_services.shared.authorization import Action, ResourceType
from grc_services.shared.exceptions import ResourceNotFoundError
from grc_tools import ToolCaller, ToolContext
from pydantic import BaseModel

from ..schemas.common import ApiModel, problem_responses
from ..security.dependencies import Authz, Context, PolicyAnalystAgentDep, PolicyHunterAgentDep

router = APIRouter(prefix="/policy-intelligence", tags=["policy-intelligence"])

# The Tool Registry's own permission check (CLAUDE.md §9) is a capability gate keyed on these
# names, distinct from the RBAC roles on ``Principal`` (CLAUDE.md §20's ``UserRole``). Every
# role that can read Policy data at all (every defined ``UserRole`` — see
# ``RbacAuthorizationService``) is granted both here, once the RBAC gate below has already run,
# rather than duplicating a second, independently-maintained role→permission table that could
# drift from it (ADR-0022).
_GRANTED_TOOL_PERMISSIONS = frozenset({"policy_hunter", "policy_analyst"})


def _tool_context(context: Context, *, agent: str) -> ToolContext:
    return ToolContext(
        caller=ToolCaller.API,
        tenant_id=str(context.organization_id),
        user_id=str(context.user_id),
        roles=_GRANTED_TOOL_PERMISSIONS,
        agent=agent,
    )


class ObligationEvidenceResponse(ApiModel):
    obligation_id: str
    obligation_text: str
    obligation_type: str
    control_domain: str
    severity: str
    suggested_policy_title: str
    classification_confidence: float
    source_id: str
    source_url: str
    citation: str


class ListObligationsResponse(BaseModel):
    obligations: list[ObligationEvidenceResponse]


class GapFindingResponse(ApiModel):
    obligation_id: str
    gap_category: str
    source_id: str
    source_url: str
    citation: str
    confidence: float
    matched_policy_id: str | None
    matched_policy_title: str | None
    rationale: str


class CoverageGapScanResponse(BaseModel):
    findings: list[GapFindingResponse]
    obligations_scanned: int
    policies_considered: int


class QualityFindingResponse(ApiModel):
    finding_type: str
    severity: str
    evidence: str
    citation: str
    recommendation: str
    confidence: float
    related_obligation_id: str | None


class PolicyQualityReviewResponse(BaseModel):
    policy_id: str
    findings: list[QualityFindingResponse]
    obligations_considered: int


@router.get(
    "/obligations",
    response_model=ListObligationsResponse,
    summary="List confirmed regulatory obligations (Policy Hunter)",
    responses=problem_responses(403),
)
async def list_obligations(
    agent: PolicyHunterAgentDep,
    authz: Authz,
    context: Context,
    control_domain: str | None = Query(default=None),
) -> ListObligationsResponse:
    await authz.ensure_can(context, Action.READ, ResourceType.POLICY)
    output = await agent.list_applicable_obligations(
        control_domain=control_domain,
        context=_tool_context(context, agent="policy_hunter_agent"),
    )
    return ListObligationsResponse(
        obligations=[ObligationEvidenceResponse.model_validate(o) for o in output.obligations]
    )


@router.get(
    "/coverage-gaps",
    response_model=CoverageGapScanResponse,
    summary="Scan this tenant's policies for regulatory coverage gaps (Policy Hunter)",
    responses=problem_responses(403),
)
async def scan_coverage_gaps(
    agent: PolicyHunterAgentDep,
    authz: Authz,
    context: Context,
    control_domain: str | None = Query(default=None),
) -> CoverageGapScanResponse:
    await authz.ensure_can(context, Action.READ, ResourceType.POLICY)
    output = await agent.scan_policy_coverage_gaps(
        tenant_id=str(context.organization_id),
        control_domain=control_domain,
        context=_tool_context(context, agent="policy_hunter_agent"),
    )
    return CoverageGapScanResponse(
        findings=[GapFindingResponse.model_validate(f) for f in output.findings],
        obligations_scanned=output.obligations_scanned,
        policies_considered=output.policies_considered,
    )


@router.get(
    "/policies/{policy_id}/quality-review",
    response_model=PolicyQualityReviewResponse,
    summary="Review one policy's quality: completeness, alignment, consistency, freshness"
    " (Policy Analyst)",
    responses=problem_responses(403, 404),
)
async def review_policy_quality(
    policy_id: str,
    agent: PolicyAnalystAgentDep,
    authz: Authz,
    context: Context,
) -> PolicyQualityReviewResponse:
    await authz.ensure_can(context, Action.READ, ResourceType.POLICY)
    try:
        output = await agent.review_policy_quality(
            tenant_id=str(context.organization_id),
            policy_id=policy_id,
            context=_tool_context(context, agent="policy_analyst_agent"),
        )
    except PolicyNotFoundError as error:
        raise ResourceNotFoundError(str(error)) from error
    return PolicyQualityReviewResponse(
        policy_id=output.policy_id,
        findings=[QualityFindingResponse.model_validate(f) for f in output.findings],
        obligations_considered=output.obligations_considered,
    )
