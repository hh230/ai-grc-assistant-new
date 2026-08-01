/**
 * Policy Intelligence application service — proxies to `apps/api`'s FastAPI Policy
 * Intelligence router (PI-P5, ADR-0022), which is the only place Policy Hunter's and Policy
 * Analyst's Tools actually run. This module never re-implements coverage-gap scanning or
 * policy-quality review in TypeScript; it authenticates the call with the actor's own
 * backend bearer token (`ActorContext.apiToken` — the bridge `lib/auth/actor.ts` already
 * documents and every seeded dev user already carries) and translates the response shape
 * into this app's camelCase domain types (CLAUDE.md §15 anti-corruption layer).
 *
 * `apps/api` remains the authorization source of truth: it re-checks RBAC and the Tool
 * Registry's own permission grant on every call regardless of what the frontend already
 * inferred from `lib/auth/permissions.ts`. A denial there surfaces here as `ForbiddenError`,
 * not swallowed or second-guessed. Node-only (server components / route handlers only).
 */

import { ForbiddenError, NotFoundError, UpstreamError, ValidationError } from "@/lib/errors";
import type { ActorContext } from "@/lib/auth/actor";
import { logger } from "@/lib/observability/logger";
import type {
  CoverageGapScan,
  GapFinding,
  ObligationEvidence,
  PolicyQualityReview,
  QualityFinding,
} from "./types";

function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

interface ProblemDetail {
  code?: string;
  detail?: string;
  title?: string;
}

async function callPolicyIntelligenceApi<T>(
  actor: ActorContext,
  path: string,
  params?: Record<string, string | undefined>,
  options: { onUnreachable?: "error" | "warn" } = {},
): Promise<T> {
  const url = new URL(`/api/v1/policy-intelligence${path}`, apiBaseUrl());
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value) url.searchParams.set(key, value);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      headers: { Authorization: `Bearer ${actor.apiToken}` },
      cache: "no-store",
    });
  } catch (error) {
    // "warn" is for read-only call sites that degrade gracefully when the backend isn't
    // deployed in this environment (see listObligations) — logged, but not reported to
    // Sentry (logger.error is the only level that reports; see logger.ts). Scan/review
    // results and any future mutating calls keep the default "error" (see the
    // graceful-degradation policy on UpstreamError in lib/errors.ts).
    if (options.onUnreachable === "warn") {
      logger.warn("policy_intelligence_upstream_unreachable", {
        url: url.toString(),
        errorMessage: error instanceof Error ? error.message : String(error),
      });
    } else {
      logger.error("policy_intelligence_upstream_unreachable", error, { url: url.toString() });
    }
    throw new UpstreamError("Could not reach the Policy Intelligence backend.", true);
  }

  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as ProblemDetail;
    const message = problem.detail ?? problem.title ?? `Request failed (${response.status}).`;
    if (response.status === 403) throw new ForbiddenError(message);
    if (response.status === 404) throw new NotFoundError(message);
    if (response.status === 422) throw new ValidationError(message);
    logger.error("policy_intelligence_upstream_error", {
      status: response.status,
      code: problem.code,
      url: url.toString(),
    });
    throw new UpstreamError(message);
  }

  return (await response.json()) as T;
}

interface ObligationEvidenceDto {
  obligation_id: string;
  obligation_text: string;
  obligation_type: string;
  control_domain: string;
  severity: string;
  suggested_policy_title: string;
  classification_confidence: number;
  source_id: string;
  source_url: string;
  citation: string;
}

function toObligationEvidence(dto: ObligationEvidenceDto): ObligationEvidence {
  return {
    obligationId: dto.obligation_id,
    obligationText: dto.obligation_text,
    obligationType: dto.obligation_type,
    controlDomain: dto.control_domain,
    severity: dto.severity as ObligationEvidence["severity"],
    suggestedPolicyTitle: dto.suggested_policy_title,
    classificationConfidence: dto.classification_confidence,
    sourceId: dto.source_id,
    sourceUrl: dto.source_url,
    citation: dto.citation,
  };
}

export async function listObligations(
  actor: ActorContext,
  controlDomain?: string,
): Promise<ObligationEvidence[]> {
  let data: { obligations: ObligationEvidenceDto[] };
  try {
    data = await callPolicyIntelligenceApi<{ obligations: ObligationEvidenceDto[] }>(
      actor,
      "/obligations",
      { control_domain: controlDomain },
      { onUnreachable: "warn" },
    );
  } catch (error) {
    // Pipeline-classified obligations list — an unreachable backend degrades to "no confirmed
    // obligations yet" instead of failing the whole workspace page (see the
    // graceful-degradation policy on UpstreamError in lib/errors.ts).
    if (error instanceof UpstreamError && error.unreachable) return [];
    throw error;
  }
  return data.obligations.map(toObligationEvidence);
}

interface GapFindingDto {
  obligation_id: string;
  gap_category: string;
  source_id: string;
  source_url: string;
  citation: string;
  confidence: number;
  matched_policy_id: string | null;
  matched_policy_title: string | null;
  rationale: string;
}

function toGapFinding(dto: GapFindingDto): GapFinding {
  return {
    obligationId: dto.obligation_id,
    gapCategory: dto.gap_category as GapFinding["gapCategory"],
    sourceId: dto.source_id,
    sourceUrl: dto.source_url,
    citation: dto.citation,
    confidence: dto.confidence,
    matchedPolicyId: dto.matched_policy_id,
    matchedPolicyTitle: dto.matched_policy_title,
    rationale: dto.rationale,
  };
}

export async function scanCoverageGaps(
  actor: ActorContext,
  controlDomain?: string,
): Promise<CoverageGapScan> {
  const data = await callPolicyIntelligenceApi<{
    findings: GapFindingDto[];
    obligations_scanned: number;
    policies_considered: number;
  }>(actor, "/coverage-gaps", { control_domain: controlDomain });
  return {
    findings: data.findings.map(toGapFinding),
    obligationsScanned: data.obligations_scanned,
    policiesConsidered: data.policies_considered,
  };
}

interface QualityFindingDto {
  finding_type: string;
  severity: string;
  evidence: string;
  citation: string;
  recommendation: string;
  confidence: number;
  related_obligation_id: string | null;
}

function toQualityFinding(dto: QualityFindingDto): QualityFinding {
  return {
    findingType: dto.finding_type as QualityFinding["findingType"],
    severity: dto.severity as QualityFinding["severity"],
    evidence: dto.evidence,
    citation: dto.citation,
    recommendation: dto.recommendation,
    confidence: dto.confidence,
    relatedObligationId: dto.related_obligation_id,
  };
}

export async function reviewPolicyQuality(
  actor: ActorContext,
  policyId: string,
): Promise<PolicyQualityReview> {
  const data = await callPolicyIntelligenceApi<{
    policy_id: string;
    findings: QualityFindingDto[];
    obligations_considered: number;
  }>(actor, `/policies/${encodeURIComponent(policyId)}/quality-review`);
  return {
    policyId: data.policy_id,
    findings: data.findings.map(toQualityFinding),
    obligationsConsidered: data.obligations_considered,
  };
}
