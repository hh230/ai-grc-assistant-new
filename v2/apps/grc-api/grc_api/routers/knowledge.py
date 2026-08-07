"""`/v1/knowledge/*` — Sector Knowledge Packs (ADR 0067).

Transport only. Every route resolves the caller, hands an Application Service its arguments, and
shapes the answer. No route decides a state transition, checks a role, or writes SQL — the services
own the first two (`knowledge_services`) and the repository owns the third.

Two audiences share the prefix and must not share a shape:

    the review console   platform-wide, `knowledge_approver` only — drafts, provenance, lifecycle
    the interview        tenant-scoped — the ACTIVE release only, and no reviewer-only text

`GET /industries/{slug}/active-release` is the one knowledge read a customer makes, and it returns
`InterviewQuestionView`, which has no `why_we_ask` field to leak.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from governance_store.knowledge_services import (
    ActivateKnowledgeRelease,
    Actor,
    ApproveKnowledgeTemplate,
    CompleteAssessment,
    GenerateKnowledgeTemplate,
    OpenSectorInterview,
    PublishKnowledgeTemplate,
    RecordSectorAnswers,
    RejectKnowledgeTemplate,
    RetireIndustry,
    StartAssessment,
    SubmitKnowledgeTemplate,
    require_knowledge_approver,
)
from pipeline_contracts import TenantContext

from grc_api.deps import (
    get_discovery_session_reader,
    get_knowledge_generation_service,
    get_knowledge_store,
    knowledge_actor,
    utc_now,
)
from grc_api.errors import ApiError
from grc_api.knowledge_schemas import (
    ActivateReleaseBody,
    ActivationHistoryResponse,
    ActivationRecordView,
    ActiveReleaseView,
    GenerateReleaseBody,
    IndustryListResponse,
    IndustryView,
    InterviewReleaseView,
    OpenSectorInterviewBody,
    OutcomeResponse,
    PlanContextResponse,
    RecordAnswersBody,
    RegisterIndustryBody,
    ReleaseListResponse,
    ReleaseView,
    SectorInterviewView,
    StartAssessmentBody,
)
from grc_api.security import require_tenant

router = APIRouter()


def _not_found(what: str, identifier: str) -> ApiError:
    return ApiError(status_code=404, code="not_found", message=f"no {what} {identifier!r}")


# --- the review console (platform-wide, knowledge_approver) -----------------------------------


@router.get("/knowledge/industries", response_model=IndustryListResponse)
def list_industries(
    _: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_knowledge_store)],
    include_retired: Annotated[bool, Query()] = False,
) -> IndustryListResponse:
    return IndustryListResponse(
        industries=[
            IndustryView(**row) for row in store.list_industries(include_retired=include_retired)
        ]
    )


@router.post("/knowledge/industries", status_code=201)
def register_industry(
    body: RegisterIndustryBody,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> dict[str, str]:
    # Registering an industry is one idempotent write with no coordination and no event — the one
    # knowledge operation with no service, because inventing one would be a class that only
    # forwards. The role is still required: an industry nobody governs is knowledge nobody owns.
    require_knowledge_approver(actor, "registering an industry")
    store.register_industry(body.slug, body.canonical_name_ar)
    return {"slug": body.slug}


@router.post("/knowledge/industries/{industry_slug}/retire", response_model=OutcomeResponse)
def retire_industry(
    industry_slug: str,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    """Stops serving the industry's active release, marks it unavailable, and retires the release —
    in that order, which is the only one the schema permits."""
    outcome = RetireIndustry(store, connection=store._conn)(
        industry_slug=industry_slug, actor=actor
    )
    return OutcomeResponse.from_outcome(outcome)


@router.post("/knowledge/releases", response_model=OutcomeResponse, status_code=201)
def generate_release(
    body: GenerateReleaseBody,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    service: Annotated[GenerateKnowledgeTemplate | None, Depends(get_knowledge_generation_service)],
) -> OutcomeResponse:
    """Calls the model **once** for the sector. Every later customer in it reads the stored release.

    `503` when no governance model is configured — this deployment cannot generate knowledge, and
    saying so is the point. The failure this refuses to repeat is the product once answering
    `"echo: <input>"` in place of a governance plan while nothing said anything was wrong.
    """
    if service is None:
        raise ApiError(
            status_code=503,
            code="unavailable",
            message=(
                "knowledge generation is not configured: the governance role has no model in this "
                "deployment"
            ),
        )
    return OutcomeResponse.from_outcome(service(industry_slug=body.industry_slug, actor=actor))


@router.get("/knowledge/releases", response_model=ReleaseListResponse)
def list_releases(
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
    industry_slug: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    with_questions: Annotated[bool, Query()] = False,
) -> ReleaseListResponse:
    """The review console's one read. A draft is unreviewed knowledge, so the role is required to
    see it at all — not only to act on it."""
    require_knowledge_approver(actor, "reading knowledge releases")
    rows = store.list_releases(
        industry_slug=industry_slug, status=status, with_questions=with_questions
    )
    return ReleaseListResponse(releases=[ReleaseView.from_row(r) for r in rows])


@router.get("/knowledge/releases/{release_id}", response_model=ReleaseView)
def get_release(
    release_id: str,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> ReleaseView:
    """One release with its questions — the same List primitive, filtered. The repository has no
    `get_release`: one method per screen is how a repository grows without limit."""
    require_knowledge_approver(actor, "reading a knowledge release")
    rows = store.list_releases(release_id=release_id, with_questions=True)
    if not rows:
        raise _not_found("release", release_id)
    return ReleaseView.from_row(rows[0])


@router.post("/knowledge/releases/{release_id}/submit", response_model=OutcomeResponse)
def submit_release(
    release_id: str,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    return OutcomeResponse.from_outcome(
        SubmitKnowledgeTemplate(store)(release_id=release_id, actor=actor)
    )


@router.post("/knowledge/releases/{release_id}/approve", response_model=OutcomeResponse)
def approve_release(
    release_id: str,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    return OutcomeResponse.from_outcome(
        ApproveKnowledgeTemplate(store, now=utc_now)(release_id=release_id, actor=actor)
    )


@router.post("/knowledge/releases/{release_id}/reject", response_model=OutcomeResponse)
def reject_release(
    release_id: str,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    return OutcomeResponse.from_outcome(
        RejectKnowledgeTemplate(store)(release_id=release_id, actor=actor)
    )


@router.post("/knowledge/releases/{release_id}/publish", response_model=OutcomeResponse)
def publish_release(
    release_id: str,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    """Publishing makes a release *eligible* for activation; it does not activate it. Keeping the
    two apart is what lets several releases be published while exactly one is live."""
    return OutcomeResponse.from_outcome(
        PublishKnowledgeTemplate(store, now=utc_now)(release_id=release_id, actor=actor)
    )


@router.put(
    "/knowledge/industries/{industry_slug}/active-release", response_model=OutcomeResponse
)
def set_active_release(
    industry_slug: str,
    body: ActivateReleaseBody,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    """`PUT`, because this sets one fact — which release is live — rather than appending an event.
    Rollback is the same call with an older release id; no release row is touched either way."""
    return OutcomeResponse.from_outcome(
        ActivateKnowledgeRelease(store)(
            industry_slug=industry_slug,
            release_id=body.release_id,
            actor=actor,
            reason=body.reason,
        )
    )


@router.get(
    "/knowledge/industries/{industry_slug}/activations", response_model=ActivationHistoryResponse
)
def list_activations(
    industry_slug: str,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> ActivationHistoryResponse:
    """"What was live at 10:30?" — append-only, and why an audit is answerable a year later."""
    require_knowledge_approver(actor, "reading activation history")
    return ActivationHistoryResponse(
        activations=[
            ActivationRecordView(
                release_id=row["release_id"],
                activated_by=row["activated_by"],
                activated_at=row["activated_at"],
                reason=row["reason"],
            )
            for row in store.list_activation_history(industry_slug)
        ]
    )


# --- the interview (tenant-scoped) ------------------------------------------------------------


@router.get(
    "/knowledge/industries/{industry_slug}/active-release", response_model=ActiveReleaseView
)
def get_active_release(
    industry_slug: str,
    _: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> ActiveReleaseView:
    """What an interview draws from. `404` when nothing is active — an interview must never be
    handed knowledge nobody activated, and a near-miss would be worse than nothing."""
    row = store.get_active_release(industry_slug)
    if row is None:
        raise _not_found("active release for industry", industry_slug)
    return ActiveReleaseView.from_row(industry_slug, row)


@router.post(
    "/knowledge/sessions/{session_id}/sector-interview", response_model=SectorInterviewView
)
def open_sector_interview(
    session_id: str,
    body: OpenSectorInterviewBody,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_knowledge_store)],
    sessions: Annotated[Any, Depends(get_discovery_session_reader)],
) -> SectorInterviewView:
    """Closes the loop: what a reviewer activated is exactly what this customer is asked.

    Idempotent by design — a customer who reloads mid-interview must reach the same assessment, not
    a second one holding half their answers. A sector with nothing activated is a NORMAL answer
    (`no_sector_pack`), not an error: most sectors will have no published pack for a long time, and
    an organization must still be able to finish.
    """
    try:
        outcome = OpenSectorInterview(
            store, sessions, connection=store._conn, new_id=lambda: str(uuid4())
        )(
            session_id=session_id,
            tenant_id=tenant.tenant_id,
            organization_id=body.organization_id,
        )
    except ValueError as exc:  # the core interview has not concluded
        raise ApiError(status_code=409, code="conflict", message=str(exc)) from exc

    status = str(outcome.data["status"])
    if status == "no_sector_pack":
        return SectorInterviewView(status=status)

    release_id = outcome.data.get("release_id")
    rows = (
        store.list_releases(release_id=str(release_id), with_questions=True) if release_id else []
    )
    if not rows:
        raise _not_found("release cited by this assessment", str(release_id))
    return SectorInterviewView(
        status=status,
        assessment_id=str(outcome.data["assessment_id"]),
        completed=outcome.data.get("completed_at") is not None,
        release=InterviewReleaseView.from_row(rows[0]),
    )


@router.post("/knowledge/assessments", response_model=OutcomeResponse, status_code=201)
def start_assessment(
    body: StartAssessmentBody,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    """The selection is the caller's, not this route's. `suggested_industry_slug` is what
    `primary_activity` proposed; `selected_release_ids` is what a human decided — and reality is
    not one sector, so it is a list."""
    return OutcomeResponse.from_outcome(
        StartAssessment(store, connection=store._conn, new_id=lambda: str(uuid4()))(
            tenant_id=tenant.tenant_id,
            organization_id=body.organization_id,
            suggested_industry_slug=body.suggested_industry_slug,
            selected_release_ids=body.selected_release_ids,
            selected_by=tenant.principal_id,
            source_session_id=body.source_session_id,
        )
    )


@router.post("/knowledge/assessments/{assessment_id}/answers", response_model=OutcomeResponse)
def record_answers(
    assessment_id: str,
    body: RecordAnswersBody,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    """All or nothing: half an interview persisted is one that cannot be interpreted."""
    return OutcomeResponse.from_outcome(
        RecordSectorAnswers(store)(
            assessment_id=assessment_id,
            tenant_id=tenant.tenant_id,
            answers=[a.model_dump() for a in body.answers],
        )
    )


@router.post("/knowledge/assessments/{assessment_id}/complete", response_model=OutcomeResponse)
def complete_assessment(
    assessment_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    """One-way. After it the schema refuses every further write to this assessment, which is what
    lets a plan be built from it without snapshot isolation."""
    return OutcomeResponse.from_outcome(
        CompleteAssessment(store, now=utc_now)(
            assessment_id=assessment_id, tenant_id=tenant.tenant_id
        )
    )


@router.get(
    "/knowledge/assessments/{assessment_id}/plan-context", response_model=PlanContextResponse
)
def get_plan_context(
    assessment_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> PlanContextResponse:
    """Concluded assessments only. `404` covers both "no such assessment" and "not yours" — telling
    a caller that an id exists but belongs to someone else confirms a fact about another customer.
    """
    try:
        context = store.load_plan_context(assessment_id, tenant_id=tenant.tenant_id)
    except ValueError as exc:  # still open — a plan context would be built on movable answers
        raise ApiError(status_code=409, code="conflict", message=str(exc)) from exc
    if context is None:
        raise _not_found("assessment", assessment_id)
    return PlanContextResponse(**context)
