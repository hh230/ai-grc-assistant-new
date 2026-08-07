/**
 * The customer's sector interview — proxies to grc-api's `/v1/knowledge/*` customer routes
 * (ADR 0067). Deliberately separate from `lib/knowledge/service.ts`: that one governs knowledge and
 * asserts an approver role; this one is a tenant reading what was activated for it, and asserts no
 * role at all. Sharing a module would put the two a typo apart.
 */

import { ForbiddenError, NotFoundError, UpstreamError, ValidationError } from "@/lib/errors";
import type { ActorContext } from "@/lib/auth/actor";
import { logger } from "@/lib/observability/logger";
import { mintGrcApiServiceToken } from "@/lib/discovery/serviceToken";
import type { SectorAnswer, SectorInterview, SectorQuestion } from "./types";

function grcApiBaseUrl(): string {
  return process.env.GRC_API_BASE_URL ?? "http://localhost:8000";
}

async function call<T>(
  actor: ActorContext,
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): Promise<T> {
  const url = new URL(`/v1/knowledge${path}`, grcApiBaseUrl());
  const token = mintGrcApiServiceToken({
    tenantId: actor.tenantId,
    principalId: actor.userId,
  });

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch (error) {
    logger.error("sector_interview_upstream_unreachable", error, { url: url.toString() });
    throw new UpstreamError("Could not reach the governance backend.", true);
  }

  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as {
      error?: { code?: string; message?: string };
    };
    const message = problem.error?.message ?? `Request failed (${response.status}).`;
    if (response.status === 403) throw new ForbiddenError(message);
    if (response.status === 404) throw new NotFoundError(message);
    if (response.status === 400 || response.status === 409) throw new ValidationError(message);
    logger.error("sector_interview_upstream_error", {
      status: response.status,
      url: url.toString(),
    });
    throw new UpstreamError(message);
  }
  return (await response.json()) as T;
}

interface QuestionDto {
  question_id: string;
  canonical_text_ar: string;
  type: string;
  options: unknown[];
  required: boolean;
  category: string;
  importance: string;
  references: { framework: string; clause?: string | null }[];
  evidence_required: string[];
}

interface InterviewDto {
  status: string;
  assessment_id: string | null;
  completed: boolean;
  source_session_id: string | null;
  release: {
    release_id: string;
    industry_slug: string;
    version: number;
    questions: QuestionDto[];
  } | null;
}

function toQuestion(dto: QuestionDto): SectorQuestion {
  return {
    questionId: dto.question_id,
    canonicalTextAr: dto.canonical_text_ar,
    type: dto.type as SectorQuestion["type"],
    options: dto.options.map(String),
    required: dto.required,
    category: dto.category,
    importance: dto.importance as SectorQuestion["importance"],
    references: dto.references.map((r) => ({
      framework: r.framework,
      ...(r.clause ? { clause: r.clause } : {}),
    })),
    evidenceRequired: dto.evidence_required,
  };
}

/**
 * Opens (or resumes) the sector stage for a concluded Discovery session. Idempotent: a customer who
 * reloads reaches the same assessment holding their answers, never a second one.
 */
export async function openSectorInterview(
  actor: ActorContext,
  sessionId: string,
  organizationId: string,
): Promise<SectorInterview> {
  const dto = await call<InterviewDto>(
    actor,
    "POST",
    `/sessions/${encodeURIComponent(sessionId)}/sector-interview`,
    { organization_id: organizationId },
  );
  return toInterview(dto);
}


function toInterview(dto: InterviewDto): SectorInterview {
  return {
    status: dto.status as SectorInterview["status"],
    assessmentId: dto.assessment_id,
    completed: dto.completed,
    sourceSessionId: dto.source_session_id ?? null,
    release: dto.release
      ? {
          releaseId: dto.release.release_id,
          industrySlug: dto.release.industry_slug,
          version: dto.release.version,
          questions: dto.release.questions.map(toQuestion),
        }
      : null,
  };
}


/**
 * The tenant's unfinished sector interview, if there is one — looked up by TENANT, because that is
 * all a returning customer has.
 *
 * They closed the tab after the core interview concluded, so they hold no session id. Without this
 * the app can only offer to start over, and their concluded session and open assessment sit
 * orphaned — which is exactly the work they would lose.
 */
export async function findOpenSectorInterview(actor: ActorContext): Promise<SectorInterview> {
  return toInterview(await call<InterviewDto>(actor, "GET", "/sector-interview/open"));
}

/** All or nothing: half an interview persisted is one that cannot be interpreted. */
export async function recordSectorAnswers(
  actor: ActorContext,
  assessmentId: string,
  answers: SectorAnswer[],
): Promise<void> {
  await call(actor, "POST", `/assessments/${encodeURIComponent(assessmentId)}/answers`, {
    answers: answers.map((a) => ({
      release_id: a.releaseId,
      question_id: a.questionId,
      answer: a.answer,
    })),
  });
}

/** One-way. After this the schema refuses every further write to the assessment, which is what
 * lets a plan be built from it without snapshot isolation. */
export async function completeSectorInterview(
  actor: ActorContext,
  assessmentId: string,
): Promise<void> {
  await call(actor, "POST", `/assessments/${encodeURIComponent(assessmentId)}/complete`);
}
