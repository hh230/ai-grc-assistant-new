/**
 * Knowledge Review Console application service — proxies to grc-api's `/v1/knowledge/*` router
 * (ADR 0067). Same proxy shape as `lib/discovery/service.ts`: a freshly-minted service assertion
 * per request, DTO → domain mapping at the boundary, typed errors out. Node-only.
 *
 * **The one thing this file decides is who holds `knowledge_approver`.** grc-api enforces the role;
 * this side decides which of *our* people are asserted to hold it. That is not a tenant role: a
 * sector's release is the interview every customer in that sector answers, so a customer's own
 * `owner` must never be able to edit it. There is deliberately no mapping from any `UserRole`.
 */

import { ForbiddenError, NotFoundError, UpstreamError, ValidationError } from "@/lib/errors";
import type { ActorContext } from "@/lib/auth/actor";
import { logger } from "@/lib/observability/logger";
import { mintGrcApiServiceToken } from "@/lib/discovery/serviceToken";
import type {
  ActivationRecord,
  AuthoredPack,
  Industry,
  KnowledgeOutcome,
  KnowledgeRelease,
  ReleaseAction,
  ReviewQuestion,
} from "./types";

const KNOWLEDGE_APPROVER_ROLE = "knowledge_approver";

/**
 * TEMPORARY BOOTSTRAP UNTIL INTERNAL IDENTITY EXISTS.
 *
 * `KNOWLEDGE_APPROVERS` is not domain and it is not infrastructure — it is bootstrap, and bootstrap
 * that survives more than one development phase becomes technical debt. **Build nothing on top of
 * it.** No feature may read this list, branch on it, or store what it returns; the only caller is
 * the decision "assert the role, or don't". When an internal-staff identity exists, this function's
 * body is replaced and nothing else changes — grc-api only ever sees the asserted role.
 *
 * Why an allow-list at all: the authority is not a tenant's to grant. Rasheed staff author the
 * questions every customer in a sector answers, so mapping it to `owner` would hand that power to
 * every customer account in the product.
 *
 * Unset means nobody: an unconfigured deployment has no knowledge reviewers, which is the correct
 * failure. It never means everybody.
 */
export function isKnowledgeApprover(actor: { userEmail: string }): boolean {
  // By email, not by user id: this list is written and checked by a human, and a list of UUIDs is
  // a list nobody can audit at a glance — the wrong character grants nothing, or the wrong person.
  const allowed = (process.env.KNOWLEDGE_APPROVERS ?? "")
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  const email = actor.userEmail.trim().toLowerCase();
  return email.length > 0 && allowed.includes(email);
}

function grcApiBaseUrl(): string {
  return process.env.GRC_API_BASE_URL ?? "http://localhost:8000";
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string };
}

async function callKnowledgeApi<T>(
  actor: ActorContext,
  method: "GET" | "POST" | "PUT",
  path: string,
  body?: unknown,
): Promise<T> {
  const url = new URL(`/v1/knowledge${path}`, grcApiBaseUrl());
  // The role is asserted only when this side has established the actor holds it. grc-api enforces
  // it again in its Application layer — this is not the check, it is the identity.
  const token = mintGrcApiServiceToken({
    tenantId: actor.tenantId,
    // The stable id, never the email or the name. `created_by` / `approved_by` / `activated_by`
    // record WHO decided, and a person's name, address and job title all change while their
    // identity does not. Storing the readable form would copy identity data into the knowledge
    // database and let the copy rot; resolving it for display is the identity service's job.
    principalId: actor.userId,
    roles: isKnowledgeApprover(actor) ? [KNOWLEDGE_APPROVER_ROLE] : [],
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
    logger.error("knowledge_upstream_unreachable", error, { url: url.toString() });
    throw new UpstreamError("Could not reach the knowledge backend.", true);
  }

  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as ErrorEnvelope;
    const message = problem.error?.message ?? `Request failed (${response.status}).`;
    if (response.status === 403) throw new ForbiddenError(message);
    if (response.status === 404) throw new NotFoundError(message);
    // 409 is a rule the schema states — activating an unpublished release, writing to a frozen
    // assessment. It is the caller's mistake, not an outage, so it reads as a validation failure.
    if (response.status === 400 || response.status === 409) throw new ValidationError(message);
    logger.error("knowledge_upstream_error", {
      status: response.status,
      code: problem.error?.code,
      url: url.toString(),
    });
    throw new UpstreamError(message);
  }

  return (await response.json()) as T;
}

// --- DTOs (snake_case, exactly as grc-api returns them) ---------------------------------------

interface QuestionDto {
  question_id: string;
  canonical_text_ar: string;
  type: string;
  options: unknown[];
  required: boolean;
  category: string;
  importance: string;
  references: { framework: string; clause?: string | null }[];
  why_we_ask: string;
  evidence_required: string[];
}

interface ReleaseDto {
  id: string;
  industry_slug: string;
  version: number;
  status: string;
  generated_by_model: string;
  prompt_version: string;
  generator_commit: string;
  created_by: string;
  approved_by: string | null;
  approved_at: string | null;
  released_at: string | null;
  questions: QuestionDto[] | null;
}

interface OutcomeDto {
  changed: boolean;
  event: string | null;
  data: Record<string, unknown>;
}

function toQuestion(dto: QuestionDto): ReviewQuestion {
  return {
    questionId: dto.question_id,
    canonicalTextAr: dto.canonical_text_ar,
    type: dto.type as ReviewQuestion["type"],
    options: dto.options.map(String),
    required: dto.required,
    category: dto.category,
    importance: dto.importance as ReviewQuestion["importance"],
    references: dto.references.map((r) => ({
      framework: r.framework,
      ...(r.clause ? { clause: r.clause } : {}),
    })),
    whyWeAsk: dto.why_we_ask,
    evidenceRequired: dto.evidence_required,
  };
}

function toRelease(dto: ReleaseDto): KnowledgeRelease {
  return {
    id: dto.id,
    industrySlug: dto.industry_slug,
    version: dto.version,
    status: dto.status as KnowledgeRelease["status"],
    generatedByModel: dto.generated_by_model,
    promptVersion: dto.prompt_version,
    generatorCommit: dto.generator_commit,
    createdBy: dto.created_by,
    approvedBy: dto.approved_by,
    approvedAt: dto.approved_at,
    releasedAt: dto.released_at,
    questions: dto.questions ? dto.questions.map(toQuestion) : null,
  };
}

// --- reads --------------------------------------------------------------------------------------

export async function listIndustries(actor: ActorContext): Promise<Industry[]> {
  const payload = await callKnowledgeApi<{
    industries: { slug: string; canonical_name_ar: string; status: string }[];
  }>(actor, "GET", "/industries?include_retired=true");
  return payload.industries.map((i) => ({
    slug: i.slug,
    canonicalNameAr: i.canonical_name_ar,
    status: i.status as Industry["status"],
  }));
}

/** Every release, newest version first per industry. The console's queue is derived from this
 * rather than fetched separately — "awaiting review" is a status filter, not another endpoint. */
export async function listReleases(actor: ActorContext): Promise<KnowledgeRelease[]> {
  const payload = await callKnowledgeApi<{ releases: ReleaseDto[] }>(actor, "GET", "/releases");
  return payload.releases.map(toRelease);
}

export async function getRelease(
  actor: ActorContext,
  releaseId: string,
): Promise<KnowledgeRelease> {
  return toRelease(
    await callKnowledgeApi<ReleaseDto>(actor, "GET", `/releases/${encodeURIComponent(releaseId)}`),
  );
}

/** Which release is live for an industry right now, or `null`. Read from the pointer, never
 * inferred from "the newest released version" — those are different questions. */
export async function getActiveReleaseId(
  actor: ActorContext,
  industrySlug: string,
): Promise<string | null> {
  try {
    const payload = await callKnowledgeApi<{ release_id: string }>(
      actor,
      "GET",
      `/industries/${encodeURIComponent(industrySlug)}/active-release`,
    );
    return payload.release_id;
  } catch (error) {
    // Nothing activated is a normal state for a sector still in review, not a failure.
    if (error instanceof NotFoundError) return null;
    throw error;
  }
}

export async function listActivations(
  actor: ActorContext,
  industrySlug: string,
): Promise<ActivationRecord[]> {
  const payload = await callKnowledgeApi<{
    activations: {
      release_id: string;
      activated_by: string;
      activated_at: string;
      reason: string;
    }[];
  }>(actor, "GET", `/industries/${encodeURIComponent(industrySlug)}/activations`);
  return payload.activations.map((a) => ({
    releaseId: a.release_id,
    activatedBy: a.activated_by,
    activatedAt: a.activated_at,
    reason: a.reason,
  }));
}

// --- writes -------------------------------------------------------------------------------------

export async function generateRelease(
  actor: ActorContext,
  industrySlug: string,
): Promise<KnowledgeOutcome> {
  return callKnowledgeApi<OutcomeDto>(actor, "POST", "/releases", {
    industry_slug: industrySlug,
  });
}

export async function actOnRelease(
  actor: ActorContext,
  releaseId: string,
  action: ReleaseAction,
): Promise<KnowledgeOutcome> {
  return callKnowledgeApi<OutcomeDto>(
    actor,
    "POST",
    `/releases/${encodeURIComponent(releaseId)}/${action}`,
  );
}

/**
 * Sets which release an industry serves — and rollback is the same call with an older release id.
 * No release row is touched either way, which is why undoing a bad publication costs one request
 * instead of a new version that exists only to reverse a mistake.
 */
export async function setActiveRelease(
  actor: ActorContext,
  industrySlug: string,
  releaseId: string,
  reason: string,
): Promise<KnowledgeOutcome> {
  return callKnowledgeApi<OutcomeDto>(
    actor,
    "PUT",
    `/industries/${encodeURIComponent(industrySlug)}/active-release`,
    { release_id: releaseId, reason },
  );
}

/** The authored packs this deployment ships — the starting point for deploying a new sector. */
export async function listAuthoredPacks(actor: ActorContext): Promise<AuthoredPack[]> {
  const payload = await callKnowledgeApi<{
    packs: {
      industry_slug: string;
      canonical_name_ar: string;
      question_count: number;
      authored_by: string;
      problem: string | null;
    }[];
  }>(actor, "GET", "/packs");
  return payload.packs.map((pack) => ({
    industrySlug: pack.industry_slug,
    canonicalNameAr: pack.canonical_name_ar,
    questionCount: pack.question_count,
    authoredBy: pack.authored_by,
    problem: pack.problem,
  }));
}

/** Imports a pack as a draft release, registering the industry if it is new. One call, because the
 * industry's existence is not a decision a human should have to make separately. */
export async function importAuthoredPack(
  actor: ActorContext,
  industrySlug: string,
): Promise<KnowledgeOutcome> {
  return callKnowledgeApi<OutcomeDto>(
    actor,
    "POST",
    `/packs/${encodeURIComponent(industrySlug)}/import`,
  );
}

export async function registerIndustry(
  actor: ActorContext,
  slug: string,
  canonicalNameAr: string,
): Promise<void> {
  await callKnowledgeApi(actor, "POST", "/industries", {
    slug,
    canonical_name_ar: canonicalNameAr,
  });
}
