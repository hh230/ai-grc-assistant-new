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

from fastapi import APIRouter, Depends, Query, Request
from governance_store.knowledge_services import (
    ActivateKnowledgeRelease,
    Actor,
    ApproveKnowledgeTemplate,
    Event,
    GenerateKnowledgeTemplate,
    ImportAuthoredPack,
    OpenSectorInterview,
    Outcome,
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
from grc_api.knowledge_generation import generator_commit
from grc_api.knowledge_schemas import (
    ActivateReleaseBody,
    ActivationHistoryResponse,
    ActivationRecordView,
    ActiveReleaseView,
    AuthoredPackListResponse,
    AuthoredPackView,
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
from grc_api.knowledge_seed import AUTHORED_BY_MODEL
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


@router.get("/knowledge/packs", response_model=AuthoredPackListResponse)
def list_authored_packs(
    actor: Annotated[Actor, Depends(knowledge_actor)],
) -> AuthoredPackListResponse:
    """The authored packs this deployment ships, whether or not they have been imported.

    Deploying a new sector should start by looking at what is available, not by remembering a slug.
    A pack that would fail on import is listed with its problem rather than hidden, so it can be
    fixed before somebody tries to deploy it.
    """
    from grc_api.knowledge_seed import describe_packs

    require_knowledge_approver(actor, "reading the authored knowledge packs")
    return AuthoredPackListResponse(
        packs=[AuthoredPackView(**pack) for pack in describe_packs()]
    )


@router.post(
    "/knowledge/packs/{industry_slug}/import",
    response_model=OutcomeResponse,
    status_code=201,
)
def import_authored_pack(
    industry_slug: str,
    actor: Annotated[Actor, Depends(knowledge_actor)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    """Imports an authored pack as a draft release, registering the industry if it is new.

    One call, because the industry's existence is not a decision a human should have to make
    separately — the pack file already declares its slug and its Arabic name. What a human still
    decides is everything that matters: whether these questions are fit to be asked.
    """
    from grc_api.knowledge_seed import AuthoredPackGenerator, AuthoredPackRejected, load_pack

    try:
        pack = load_pack(industry_slug)
    except AuthoredPackRejected as exc:
        # The pack file is wrong, not the request — say which question, not which constraint.
        raise ApiError(status_code=422, code="validation_error", message=str(exc)) from exc

    service = ImportAuthoredPack(
        store,
        AuthoredPackGenerator(),
        new_id=lambda: str(uuid4()),
        model=AUTHORED_BY_MODEL,
        prompt_version=f"authored:{industry_slug}",
        generator_commit=generator_commit(),
    )
    return OutcomeResponse.from_outcome(
        service(
            industry_slug=industry_slug,
            canonical_name_ar=str(pack.get("canonical_name_ar", industry_slug)),
            actor=actor,
        )
    )


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


def _saved_answers(store: Any, assessment_id: str, tenant_id: str) -> dict[str, Any]:
    """What has been answered so far, keyed by question. The client resumes from this."""
    rows = store.list_sector_answers(assessment_id, tenant_id=tenant_id)
    return {str(row["question_id"]): row["answer"] for row in rows}


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
    assessment_id = str(outcome.data["assessment_id"])
    return SectorInterviewView(
        status=status,
        assessment_id=assessment_id,
        completed=outcome.data.get("completed_at") is not None,
        release=InterviewReleaseView.from_row(rows[0]),
        answers=_saved_answers(store, assessment_id, tenant.tenant_id),
    )


@router.get("/knowledge/sector-interview/open", response_model=SectorInterviewView)
def resume_sector_interview(
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> SectorInterviewView:
    """The tenant's unfinished sector interview, if there is one.

    Looked up by TENANT, because that is all a returning customer has. They closed the tab after
    the core interview concluded; they hold no session id, and without this their answers are
    unreachable and the only way forward is to start the whole interview again.

    `no_sector_pack` when there is nothing to resume — a status, not a `404`, because "you have no
    unfinished interview" is a normal answer to this question and the client continues rather than
    treating it as an error.
    """
    assessment = store.find_open_assessment(tenant_id=tenant.tenant_id)
    if assessment is None:
        return SectorInterviewView(status="no_sector_pack")

    selection = store.get_selection(assessment["id"], tenant_id=tenant.tenant_id)
    cited = (selection or {}).get("selected_release_ids") or []
    rows = store.list_releases(release_id=cited[0], with_questions=True) if cited else []
    if not rows:
        # An assessment with no readable selection cannot be resumed into questions. Reported as
        # nothing to resume rather than as an error: the customer must still be able to proceed.
        return SectorInterviewView(status="no_sector_pack")
    return SectorInterviewView(
        status="already_open",
        assessment_id=assessment["id"],
        completed=False,
        source_session_id=assessment["source_session_id"],
        release=InterviewReleaseView.from_row(rows[0]),
        answers=_saved_answers(store, assessment["id"], tenant.tenant_id),
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
    """Idempotent per question, which is what lets the client call it on every answer.

    An earlier version of this docstring said "all or nothing", written when the whole interview
    was submitted at the end. That was never a property of the endpoint — it was a description of
    its only caller. Re-answering a question REPLACES it, so saving one answer and saving twenty
    are the same operation, and a customer who closes the tab at question nine keeps nine answers
    instead of none.

    An assessment still becomes a plan only when it is COMPLETED. Saving an answer moves nothing
    forward; it only means the answer is no longer held in a browser.
    """
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
    request: Request,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
    store: Annotated[Any, Depends(get_knowledge_store)],
) -> OutcomeResponse:
    """One-way. After it the schema refuses every further write to this assessment, which is what
    lets a plan be built from it without snapshot isolation.

    It is also the single recomputation point (ADR 0068 §D5): any answer that DECLARED an engine
    signal is merged here, once, and the resulting analysis is recorded as a new applicability
    version. An interview whose questions declared nothing — every shipped pack today — takes the
    original path and records no version, so the decision stays exactly where discovery left it.
    """
    from governance_store.store import PostgresGovernanceStore

    from grc_api.sector_conclusion import AlreadyConcluded, conclude_sector_assessment

    try:
        result = conclude_sector_assessment(
            connection=store._conn,
            knowledge_store=store,
            governance_store=PostgresGovernanceStore(connection=store._conn),
            engine=request.app.state.discovery_engine,
            assessment_id=assessment_id,
            tenant_id=tenant.tenant_id,
            now=utc_now(),
        )
    except LookupError:
        # Invisible to this tenant. Reported as "nothing changed" rather than 404, preserving the
        # existing contract: an assessment id is a fact about another customer, and a status code
        # that distinguishes "yours, already done" from "not yours" would leak it.
        return OutcomeResponse.from_outcome(
            Outcome(changed=False, data={"assessment_id": assessment_id})
        )
    except AlreadyConcluded:
        # Not an error the caller can fix by retrying, and not a 500: the assessment is already in
        # the state they asked for. Reported as unchanged, the same shape `CompleteAssessment`
        # returned when it was called twice.
        return OutcomeResponse.from_outcome(
            Outcome(changed=False, data={"assessment_id": assessment_id})
        )

    return OutcomeResponse.from_outcome(
        Outcome(
            changed=True,
            event=Event(
                "AssessmentCompleted",
                {
                    "assessment_id": assessment_id,
                    "tenant_id": tenant.tenant_id,
                    "applicability_version_id": result.version_id,
                    "conflict_count": len(result.conflicts),
                },
            ),
            data={
                "assessment_id": assessment_id,
                "applicability_version_id": result.version_id,
                "conflicts": list(result.conflicts),
            },
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
