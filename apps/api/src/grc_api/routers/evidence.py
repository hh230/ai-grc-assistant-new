"""Evidence router — collection, validation, and control linkage (CLAUDE.md §11)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from grc_domain.evidence.enums import EvidenceType
from grc_domain.shared.identifiers import ControlId, EvidenceId, KnowledgeSourceId
from grc_services.evidence import commands as c
from grc_services.evidence import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/evidence", tags=["evidence"])


class EvidenceResponse(ApiModel):
    id: str
    organization_id: str
    title: str
    evidence_type: str
    status: str
    knowledge_source_id: str | None
    linked_control_ids: list[str]


class CollectEvidenceRequest(ApiModel):
    title: str = Field(min_length=1)
    evidence_type: EvidenceType
    knowledge_source_id: str | None = None


class RejectEvidenceRequest(ApiModel):
    reason: str = Field(min_length=1)


class LinkControlRequest(ApiModel):
    control_id: str = Field(min_length=1)


@router.post(
    "",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Collect evidence",
    responses=problem_responses(403, 422),
)
async def collect_evidence(
    body: CollectEvidenceRequest, commands: Commands, context: Context
) -> object:
    command = c.CollectEvidence(
        title=body.title,
        evidence_type=body.evidence_type,
        knowledge_source_id=(
            KnowledgeSourceId(body.knowledge_source_id) if body.knowledge_source_id else None
        ),
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[EvidenceResponse],
    summary="List evidence linked to a control",
    responses=problem_responses(403),
)
async def list_evidence(queries: Queries, context: Context, control_id: str = Query(...)) -> object:
    query = q.ListEvidenceForControl(control_id=ControlId(control_id))
    return unwrap(await queries.ask(query, context))


@router.get(
    "/{evidence_id}",
    response_model=EvidenceResponse,
    summary="Get an evidence item",
    responses=problem_responses(403, 404),
)
async def get_evidence(evidence_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.GetEvidence(evidence_id=EvidenceId(evidence_id)), context))


@router.post(
    "/{evidence_id}/validate",
    response_model=EvidenceResponse,
    summary="Validate an evidence item",
    responses=problem_responses(403, 404, 409),
)
async def validate_evidence(evidence_id: str, commands: Commands, context: Context) -> object:
    command = c.ValidateEvidence(evidence_id=EvidenceId(evidence_id))
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{evidence_id}/reject",
    response_model=EvidenceResponse,
    summary="Reject an evidence item",
    responses=problem_responses(403, 404, 409, 422),
)
async def reject_evidence(
    evidence_id: str, body: RejectEvidenceRequest, commands: Commands, context: Context
) -> object:
    command = c.RejectEvidence(evidence_id=EvidenceId(evidence_id), reason=body.reason)
    return unwrap(await commands.dispatch(command, context))


@router.post(
    "/{evidence_id}/control-links",
    response_model=EvidenceResponse,
    summary="Link evidence to a control",
    responses=problem_responses(403, 404, 422),
)
async def link_to_control(
    evidence_id: str, body: LinkControlRequest, commands: Commands, context: Context
) -> object:
    command = c.LinkEvidenceToControl(
        evidence_id=EvidenceId(evidence_id), control_id=ControlId(body.control_id)
    )
    return unwrap(await commands.dispatch(command, context))
