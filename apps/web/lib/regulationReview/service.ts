/**
 * Regulation Review application service (Knowledge Intelligence KI-P7, ADR-0031) — proxies to
 * `apps/api`'s FastAPI `/regulation-review/*` router, the only place the Saudi Regulations
 * Ingestion Pipeline's (KI-P6, ADR-0030) pending-review queue actually lives. Mirrors
 * `lib/knowledgeWorker/service.ts` exactly: never re-implements approval/embedding logic here;
 * authenticates with the actor's own backend bearer token (`ActorContext.apiToken`) and
 * translates the response shape into this app's camelCase domain types (CLAUDE.md §15
 * anti-corruption layer).
 *
 * `apps/api` remains the authorization source of truth: it re-checks RBAC (admin-only decide,
 * auditor read-only) on every call regardless of what the frontend already inferred from
 * `lib/auth/permissions.ts`. Node-only (server components / route handlers only).
 */

import { ForbiddenError, NotFoundError, UpstreamError, ValidationError } from "@/lib/errors";
import type { ActorContext } from "@/lib/auth/actor";
import { logger } from "@/lib/observability/logger";
import type {
  ApproveRegulationResult,
  PendingRegulationVersion,
  RegulationDocument,
  RegulationSection,
  RegulationSourceSummary,
  RegulationVersionDetail,
  RejectRegulationResult,
} from "./types";

function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

interface ProblemDetail {
  code?: string;
  detail?: string;
  title?: string;
}

async function callRegulationReviewApi<T>(
  actor: ActorContext,
  method: "GET" | "POST",
  path: string,
): Promise<T> {
  const url = new URL(`/api/v1/regulation-review${path}`, apiBaseUrl());

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: { Authorization: `Bearer ${actor.apiToken}` },
      cache: "no-store",
    });
  } catch (error) {
    logger.error("regulation_review_upstream_unreachable", { url: url.toString(), error });
    throw new UpstreamError("Could not reach the Regulation Review backend.");
  }

  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as ProblemDetail;
    const message = problem.detail ?? problem.title ?? `Request failed (${response.status}).`;
    if (response.status === 403) throw new ForbiddenError(message);
    if (response.status === 404) throw new NotFoundError(message);
    if (response.status === 409) throw new ValidationError(message);
    if (response.status === 422) throw new ValidationError(message);
    logger.error("regulation_review_upstream_error", {
      status: response.status,
      code: problem.code,
      url: url.toString(),
    });
    throw new UpstreamError(message);
  }

  return (await response.json()) as T;
}

interface RegulationSourceSummaryDto {
  id: string;
  short_code: string;
  title_ar: string;
  title_en: string | null;
  authority: string;
  jurisdiction: string;
  knowledge_domain: string;
  document_type: string;
  boe_source_url: string;
}

function toSourceSummary(dto: RegulationSourceSummaryDto): RegulationSourceSummary {
  return {
    id: dto.id,
    shortCode: dto.short_code,
    titleAr: dto.title_ar,
    titleEn: dto.title_en,
    authority: dto.authority,
    jurisdiction: dto.jurisdiction,
    knowledgeDomain: dto.knowledge_domain,
    documentType: dto.document_type,
    boeSourceUrl: dto.boe_source_url,
  };
}

interface PendingRegulationVersionDto {
  version_id: string;
  version_label: string;
  status: string;
  official_citation: string | null;
  content_hash: string;
  created_at: string;
  source: RegulationSourceSummaryDto;
}

function toPendingVersion(dto: PendingRegulationVersionDto): PendingRegulationVersion {
  return {
    versionId: dto.version_id,
    versionLabel: dto.version_label,
    status: dto.status,
    officialCitation: dto.official_citation,
    contentHash: dto.content_hash,
    createdAt: dto.created_at,
    source: toSourceSummary(dto.source),
  };
}

export async function listPendingRegulationVersions(
  actor: ActorContext,
): Promise<PendingRegulationVersion[]> {
  const dtos = await callRegulationReviewApi<PendingRegulationVersionDto[]>(
    actor,
    "GET",
    "/pending",
  );
  return dtos.map(toPendingVersion);
}

interface RegulationSectionDto {
  id: string;
  section_type: string;
  code: string;
  path: string[];
  title_ar: string | null;
  title_en: string | null;
  text_ar: string | null;
  text_en: string | null;
  position: number;
  parent_section_id: string | null;
  amendment_note_ar: string | null;
  amendment_note_en: string | null;
}

function toSection(dto: RegulationSectionDto): RegulationSection {
  return {
    id: dto.id,
    sectionType: dto.section_type,
    code: dto.code,
    path: dto.path,
    titleAr: dto.title_ar,
    titleEn: dto.title_en,
    textAr: dto.text_ar,
    textEn: dto.text_en,
    position: dto.position,
    parentSectionId: dto.parent_section_id,
    amendmentNoteAr: dto.amendment_note_ar,
    amendmentNoteEn: dto.amendment_note_en,
  };
}

interface RegulationDocumentDto {
  id: string;
  language: string;
  document_format: string;
  source_url: string;
  sections: RegulationSectionDto[];
}

function toDocument(dto: RegulationDocumentDto): RegulationDocument {
  return {
    id: dto.id,
    language: dto.language,
    documentFormat: dto.document_format,
    sourceUrl: dto.source_url,
    sections: dto.sections.map(toSection),
  };
}

interface RegulationVersionDetailDto {
  version_id: string;
  version_label: string;
  status: string;
  official_citation: string | null;
  content_hash: string;
  created_at: string;
  source: RegulationSourceSummaryDto;
  documents: RegulationDocumentDto[];
}

export async function getRegulationVersionDetail(
  actor: ActorContext,
  versionId: string,
): Promise<RegulationVersionDetail> {
  const dto = await callRegulationReviewApi<RegulationVersionDetailDto>(
    actor,
    "GET",
    `/${encodeURIComponent(versionId)}`,
  );
  return {
    versionId: dto.version_id,
    versionLabel: dto.version_label,
    status: dto.status,
    officialCitation: dto.official_citation,
    contentHash: dto.content_hash,
    createdAt: dto.created_at,
    source: toSourceSummary(dto.source),
    documents: dto.documents.map(toDocument),
  };
}

interface ApproveRegulationResultDto {
  version_id: string;
  status: string;
  approved_by: string | null;
  approved_at: string | null;
  sections_embedded: number;
  sections_failed: number;
}

export async function approveRegulationVersion(
  actor: ActorContext,
  versionId: string,
): Promise<ApproveRegulationResult> {
  const dto = await callRegulationReviewApi<ApproveRegulationResultDto>(
    actor,
    "POST",
    `/${encodeURIComponent(versionId)}/approve`,
  );
  return {
    versionId: dto.version_id,
    status: dto.status,
    approvedBy: dto.approved_by,
    approvedAt: dto.approved_at,
    sectionsEmbedded: dto.sections_embedded,
    sectionsFailed: dto.sections_failed,
  };
}

interface RejectRegulationResultDto {
  version_id: string;
  status: string;
}

export async function rejectRegulationVersion(
  actor: ActorContext,
  versionId: string,
): Promise<RejectRegulationResult> {
  const dto = await callRegulationReviewApi<RejectRegulationResultDto>(
    actor,
    "POST",
    `/${encodeURIComponent(versionId)}/reject`,
  );
  return { versionId: dto.version_id, status: dto.status };
}
