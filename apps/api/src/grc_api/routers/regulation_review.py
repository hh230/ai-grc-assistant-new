"""Admin Regulation Review queue (Knowledge Intelligence KI-P7, ADR-0031) — the human approval
gate over the Saudi Regulations Ingestion Pipeline (KI-P6, ADR-0030). Every version the pipeline
fetches lands ``status = 'in_review'``; nothing is embedded or exposed to RAG/search until an
admin explicitly approves it here (CLAUDE.md §9: propose, don't auto-apply).

Every route requires ``ResourceType.REGULATION_REVIEW``, deliberately left out of the
``_OPERATIONAL``/``_CATALOG`` grant sets in ``RbacAuthorizationService`` (CLAUDE.md §20) —
``OWNER``/``ADMIN`` hold every action on it; ``AUDITOR`` inherits its existing platform-wide
*read-only* grant so it can review the queue but never approve/reject; every other role gets a
403 on every route. Mirrors ``routers/knowledge_worker.py`` (KI-P5, ADR-0029) exactly: talks
directly to ``grc_persistence_web`` repositories against apps/web's live schema rather than the
gated command/query bus, since this state is platform-scope, not a tenant-owned aggregate.

Approval triggers embedding generation for that version's sections (KI-P7's other half): each
section with real article text and no embedding yet is embedded via the injected
``EmbeddingModel`` and the vector is written back. This task deliberately does **not** wire
those embeddings into any retrieval path — no RAG/search code is touched here; the retrieval-
priority merge (internal regulations DB -> trusted sources -> LLM) is tracked separately
(ADR-0032, Proposed) rather than folded into this change.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from grc_llm import EmbeddingModel
from grc_persistence_web import (
    RegulationDocumentRepository,
    RegulationSectionRepository,
    RegulationSourceRepository,
)
from grc_services.shared.authorization import Action, ResourceType
from grc_services.shared.exceptions import ConflictError, ResourceNotFoundError

from ..observability import get_logger
from ..schemas.common import ApiModel, problem_responses
from ..security.dependencies import (
    Authz,
    Context,
    EmbeddingModelDep,
    WebRegulationDocumentRepository,
    WebRegulationSectionRepository,
    WebRegulationSourceRepository,
    WebRegulationSourceVersionRepository,
)

router = APIRouter(prefix="/regulation-review", tags=["regulation-review"])

_logger = get_logger("grc_api.regulation_review")


class RegulationSourceSummary(ApiModel):
    id: str
    short_code: str
    title_ar: str
    title_en: str | None
    authority: str
    jurisdiction: str
    knowledge_domain: str
    document_type: str
    boe_source_url: str


class PendingRegulationVersionResponse(ApiModel):
    version_id: str
    version_label: str
    status: str
    official_citation: str | None
    content_hash: str
    created_at: datetime
    source: RegulationSourceSummary


class RegulationSectionResponse(ApiModel):
    id: str
    section_type: str
    code: str
    path: list[str]
    title_ar: str | None
    title_en: str | None
    text_ar: str | None
    text_en: str | None
    position: int
    parent_section_id: str | None
    amendment_note_ar: str | None
    amendment_note_en: str | None


class RegulationDocumentResponse(ApiModel):
    id: str
    language: str
    document_format: str
    source_url: str
    sections: list[RegulationSectionResponse]


class RegulationVersionDetailResponse(ApiModel):
    version_id: str
    version_label: str
    status: str
    official_citation: str | None
    content_hash: str
    created_at: datetime
    source: RegulationSourceSummary
    documents: list[RegulationDocumentResponse]


class ApproveRegulationResponse(ApiModel):
    version_id: str
    status: str
    approved_by: str | None
    approved_at: datetime | None
    sections_embedded: int
    sections_failed: int


class RejectRegulationResponse(ApiModel):
    version_id: str
    status: str


async def _load_source_summary(
    sources_repo: RegulationSourceRepository, source_id: str
) -> RegulationSourceSummary:
    source = await sources_repo.get_by_id(source_id)
    if source is None:  # pragma: no cover - FK integrity guarantees this in practice
        raise ResourceNotFoundError(f"regulation source {source_id!r} not found")
    return RegulationSourceSummary.model_validate(source)


@router.get(
    "/pending",
    response_model=list[PendingRegulationVersionResponse],
    summary="List regulation versions awaiting admin approval",
    responses=problem_responses(403),
)
async def list_pending(
    authz: Authz,
    context: Context,
    versions_repo: WebRegulationSourceVersionRepository,
    sources_repo: WebRegulationSourceRepository,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PendingRegulationVersionResponse]:
    await authz.ensure_can(context, Action.READ, ResourceType.REGULATION_REVIEW)
    versions = await versions_repo.list_pending(limit=limit)
    return [
        PendingRegulationVersionResponse(
            version_id=version.id,
            version_label=version.version_label,
            status=version.status,
            official_citation=version.official_citation,
            content_hash=version.content_hash,
            created_at=version.created_at,
            source=await _load_source_summary(sources_repo, version.source_id),
        )
        for version in versions
    ]


@router.get(
    "/{version_id}",
    response_model=RegulationVersionDetailResponse,
    summary="Get one regulation version's full extracted content for review",
    responses=problem_responses(403, 404),
)
async def get_version_detail(
    version_id: str,
    authz: Authz,
    context: Context,
    versions_repo: WebRegulationSourceVersionRepository,
    sources_repo: WebRegulationSourceRepository,
    documents_repo: WebRegulationDocumentRepository,
    sections_repo: WebRegulationSectionRepository,
) -> RegulationVersionDetailResponse:
    await authz.ensure_can(context, Action.READ, ResourceType.REGULATION_REVIEW)
    version = await versions_repo.get_by_id(version_id)
    if version is None:
        raise ResourceNotFoundError(f"regulation version {version_id!r} not found")

    documents = await documents_repo.list_for_version(version_id)
    document_responses = []
    for document in documents:
        sections = await sections_repo.list_for_document(document.id)
        document_responses.append(
            RegulationDocumentResponse(
                id=document.id,
                language=document.language,
                document_format=document.document_format,
                source_url=document.source_url,
                sections=[RegulationSectionResponse.model_validate(s) for s in sections],
            )
        )

    return RegulationVersionDetailResponse(
        version_id=version.id,
        version_label=version.version_label,
        status=version.status,
        official_citation=version.official_citation,
        content_hash=version.content_hash,
        created_at=version.created_at,
        source=await _load_source_summary(sources_repo, version.source_id),
        documents=document_responses,
    )


async def _embed_version_sections(
    version_id: str,
    *,
    documents_repo: RegulationDocumentRepository,
    sections_repo: RegulationSectionRepository,
    embedding_model: EmbeddingModel,
) -> tuple[int, int]:
    """Embeds every not-yet-embedded, real-text section of an approved version. One document's
    embedding failure is logged and counted, never allowed to leave the version un-approved or
    block another document's sections (CLAUDE.md §16) — a partial failure is surfaced in the
    response so an admin knows a retry (re-calling this same approve route, idempotent via
    ``list_needing_embedding``) is needed, rather than silently under-delivering."""
    embedded = 0
    failed = 0
    documents = await documents_repo.list_for_version(version_id)
    for document in documents:
        candidates = await sections_repo.list_needing_embedding(document.id)
        if not candidates:
            continue
        try:
            result = await embedding_model.embed([candidate.text_ar for candidate in candidates])
        except Exception:  # noqa: BLE001 - isolated per document; surfaced via the count below
            _logger.exception(
                "regulation_review.embedding_failed",
                extra={"version_id": version_id, "document_id": document.id},
            )
            failed += len(candidates)
            continue
        for candidate, vector in zip(candidates, result.vectors, strict=True):
            await sections_repo.set_embedding(candidate.id, embedding=vector, model=result.model)
            embedded += 1
    return embedded, failed


@router.post(
    "/{version_id}/approve",
    response_model=ApproveRegulationResponse,
    summary="Approve a pending regulation version and generate its section embeddings",
    responses=problem_responses(403, 404, 409),
)
async def approve_version(
    version_id: str,
    authz: Authz,
    context: Context,
    versions_repo: WebRegulationSourceVersionRepository,
    documents_repo: WebRegulationDocumentRepository,
    sections_repo: WebRegulationSectionRepository,
    embedding_model: EmbeddingModelDep,
) -> ApproveRegulationResponse:
    await authz.ensure_can(context, Action.APPROVE, ResourceType.REGULATION_REVIEW)
    actor_user_id = str(context.user_id)

    existing = await versions_repo.get_by_id(version_id)
    if existing is None:
        raise ResourceNotFoundError(f"regulation version {version_id!r} not found")

    approved = await versions_repo.approve(version_id, approved_by=actor_user_id)
    if approved is None:
        raise ConflictError(
            f"regulation version {version_id!r} is not awaiting review "
            f"(current status: {existing.status!r})"
        )

    _logger.info("regulation_review.approved", extra={"version_id": version_id})
    sections_embedded, sections_failed = await _embed_version_sections(
        version_id,
        documents_repo=documents_repo,
        sections_repo=sections_repo,
        embedding_model=embedding_model,
    )
    return ApproveRegulationResponse(
        version_id=approved.id,
        status=approved.status,
        approved_by=approved.approved_by,
        approved_at=approved.approved_at,
        sections_embedded=sections_embedded,
        sections_failed=sections_failed,
    )


@router.post(
    "/{version_id}/reject",
    response_model=RejectRegulationResponse,
    summary="Reject a pending regulation version",
    responses=problem_responses(403, 404, 409),
)
async def reject_version(
    version_id: str,
    authz: Authz,
    context: Context,
    versions_repo: WebRegulationSourceVersionRepository,
) -> RejectRegulationResponse:
    await authz.ensure_can(context, Action.APPROVE, ResourceType.REGULATION_REVIEW)

    existing = await versions_repo.get_by_id(version_id)
    if existing is None:
        raise ResourceNotFoundError(f"regulation version {version_id!r} not found")

    rejected = await versions_repo.reject(version_id)
    if rejected is None:
        raise ConflictError(
            f"regulation version {version_id!r} is not awaiting review "
            f"(current status: {existing.status!r})"
        )
    _logger.info("regulation_review.rejected", extra={"version_id": version_id})
    return RejectRegulationResponse(version_id=rejected.id, status=rejected.status)
