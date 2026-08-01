/**
 * AI Worker Control Center application service (Knowledge Intelligence KI-P5, ADR-0029) —
 * proxies to `apps/api`'s FastAPI `/knowledge-worker/*` router, the only place the
 * Autonomous Knowledge Worker's control state (`worker_control`/`worker_run_history`/
 * `worker_events`) actually lives. Never re-implements status/reporting logic here;
 * authenticates with the actor's own backend bearer token (`ActorContext.apiToken`) and
 * translates the response shape into this app's camelCase domain types (CLAUDE.md §15
 * anti-corruption layer).
 *
 * `apps/api` remains the authorization source of truth: it re-checks RBAC (admin-only) on
 * every call regardless of what the frontend already inferred from `lib/auth/permissions.ts`.
 * A denial there surfaces here as `ForbiddenError`, not swallowed or second-guessed.
 * Node-only (server components / route handlers only).
 */

import { ForbiddenError, NotFoundError, UpstreamError, ValidationError } from "@/lib/errors";
import type { ActorContext } from "@/lib/auth/actor";
import { logger } from "@/lib/observability/logger";
import type {
  LearningReports,
  ScheduleUpdate,
  WorkerControl,
  WorkerEvent,
  WorkerRun,
  WorkerStatus,
} from "./types";

function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

interface ProblemDetail {
  code?: string;
  detail?: string;
  title?: string;
}

async function callKnowledgeWorkerApi<T>(
  actor: ActorContext,
  method: "GET" | "POST",
  path: string,
  body?: unknown,
  options: { onUnreachable?: "error" | "warn" } = {},
): Promise<T> {
  const url = new URL(`/api/v1/knowledge-worker${path}`, apiBaseUrl());

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: {
        Authorization: `Bearer ${actor.apiToken}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch (error) {
    // "warn" is for read-only call sites that degrade gracefully when the backend isn't
    // deployed in this environment (see getLearningReports) — logged, but not reported to
    // Sentry (logger.error is the only level that reports; see logger.ts). Consequential
    // calls (schedule/trigger) keep the default "error" so a live backend actually going
    // unreachable still alerts.
    if (options.onUnreachable === "warn") {
      logger.warn("knowledge_worker_upstream_unreachable", {
        url: url.toString(),
        errorMessage: error instanceof Error ? error.message : String(error),
      });
    } else {
      logger.error("knowledge_worker_upstream_unreachable", error, { url: url.toString() });
    }
    throw new UpstreamError("Could not reach the AI Worker Control Center backend.", true);
  }

  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as ProblemDetail;
    const message = problem.detail ?? problem.title ?? `Request failed (${response.status}).`;
    if (response.status === 403) throw new ForbiddenError(message);
    if (response.status === 404) throw new NotFoundError(message);
    if (response.status === 422) throw new ValidationError(message);
    logger.error("knowledge_worker_upstream_error", {
      status: response.status,
      code: problem.code,
      url: url.toString(),
    });
    throw new UpstreamError(message);
  }

  return (await response.json()) as T;
}

interface WorkerStatusDto {
  enabled: boolean;
  running: boolean;
  current_cycle: "idle" | "in_progress";
  current_task: string | null;
  interval_hours: number;
  manual_trigger_requested: boolean;
  last_run_at: string | null;
  last_run_reason: string | null;
  next_run_at: string | null;
  updated_by: string | null;
  updated_at: string;
}

function toWorkerStatus(dto: WorkerStatusDto): WorkerStatus {
  return {
    enabled: dto.enabled,
    running: dto.running,
    currentCycle: dto.current_cycle,
    currentTask: dto.current_task,
    intervalHours: dto.interval_hours,
    manualTriggerRequested: dto.manual_trigger_requested,
    lastRunAt: dto.last_run_at,
    lastRunReason: dto.last_run_reason,
    nextRunAt: dto.next_run_at,
    updatedBy: dto.updated_by,
    updatedAt: dto.updated_at,
  };
}

export async function getWorkerStatus(actor: ActorContext): Promise<WorkerStatus> {
  const dto = await callKnowledgeWorkerApi<WorkerStatusDto>(actor, "GET", "/status");
  return toWorkerStatus(dto);
}

interface WorkerEventDto {
  id: string;
  event_type: WorkerEvent["eventType"];
  question_id: string | null;
  message: string;
  metadata: Record<string, string>;
  actor_user_id: string | null;
  actor_tenant_id: string | null;
  occurred_at: string;
}

function toWorkerEvent(dto: WorkerEventDto): WorkerEvent {
  return {
    id: dto.id,
    eventType: dto.event_type,
    questionId: dto.question_id,
    message: dto.message,
    metadata: dto.metadata,
    actorUserId: dto.actor_user_id,
    actorTenantId: dto.actor_tenant_id,
    occurredAt: dto.occurred_at,
  };
}

export async function listWorkerEvents(
  actor: ActorContext,
  limit?: number,
): Promise<WorkerEvent[]> {
  const path = limit ? `/events?limit=${encodeURIComponent(String(limit))}` : "/events";
  let dtos: WorkerEventDto[];
  try {
    dtos = await callKnowledgeWorkerApi<WorkerEventDto[]>(actor, "GET", path, undefined, {
      onUnreachable: "warn",
    });
  } catch (error) {
    // Pure activity-audit list — an unreachable backend degrades to "no recent activity"
    // instead of failing the whole workspace page (see the graceful-degradation policy on
    // UpstreamError in lib/errors.ts).
    if (error instanceof UpstreamError && error.unreachable) return [];
    throw error;
  }
  return dtos.map(toWorkerEvent);
}

interface WorkerRunDto {
  id: string;
  reason: string;
  started_at: string;
  completed_at: string | null;
  questions_considered: number;
  gaps_detected: number;
  items_saved: number;
  error_count: number;
}

function toWorkerRun(dto: WorkerRunDto): WorkerRun {
  return {
    id: dto.id,
    reason: dto.reason,
    startedAt: dto.started_at,
    completedAt: dto.completed_at,
    questionsConsidered: dto.questions_considered,
    gapsDetected: dto.gaps_detected,
    itemsSaved: dto.items_saved,
    errorCount: dto.error_count,
  };
}

export async function listWorkerRuns(actor: ActorContext, limit?: number): Promise<WorkerRun[]> {
  const path = limit ? `/runs?limit=${encodeURIComponent(String(limit))}` : "/runs";
  let dtos: WorkerRunDto[];
  try {
    dtos = await callKnowledgeWorkerApi<WorkerRunDto[]>(actor, "GET", path, undefined, {
      onUnreachable: "warn",
    });
  } catch (error) {
    // Pure run-history list — same graceful-degradation policy as listWorkerEvents above.
    if (error instanceof UpstreamError && error.unreachable) return [];
    throw error;
  }
  return dtos.map(toWorkerRun);
}

interface LearningReportsDto {
  total_items: number;
  verified: number;
  needs_review: number;
  outdated: number;
  discovered: number;
  added_this_cycle: number;
  updated: number;
}

const EMPTY_LEARNING_REPORTS: LearningReports = {
  totalItems: 0,
  verified: 0,
  needsReview: 0,
  outdated: 0,
  discovered: 0,
  addedThisCycle: 0,
  updated: 0,
};

export async function getLearningReports(actor: ActorContext): Promise<LearningReports> {
  let dto: LearningReportsDto;
  try {
    dto = await callKnowledgeWorkerApi<LearningReportsDto>(actor, "GET", "/reports", undefined, {
      onUnreachable: "warn",
    });
  } catch (error) {
    // The backend not being reachable (e.g. apps/api isn't deployed in this environment) is a
    // known, expected condition for this read-only report — degrade to all-zero counts instead
    // of failing the whole workspace page. A genuinely misbehaving (but reachable) backend
    // still throws below, since that's worth alerting on.
    if (error instanceof UpstreamError && error.unreachable) return EMPTY_LEARNING_REPORTS;
    throw error;
  }
  return {
    totalItems: dto.total_items,
    verified: dto.verified,
    needsReview: dto.needs_review,
    outdated: dto.outdated,
    discovered: dto.discovered,
    addedThisCycle: dto.added_this_cycle,
    updated: dto.updated,
  };
}

interface WorkerControlDto {
  id: string;
  enabled: boolean;
  interval_hours: number;
  manual_trigger_requested_at: string | null;
  updated_at: string;
  updated_by: string | null;
}

function toWorkerControl(dto: WorkerControlDto): WorkerControl {
  return {
    id: dto.id,
    enabled: dto.enabled,
    intervalHours: dto.interval_hours,
    manualTriggerRequestedAt: dto.manual_trigger_requested_at,
    updatedAt: dto.updated_at,
    updatedBy: dto.updated_by,
  };
}

export async function updateWorkerSchedule(
  actor: ActorContext,
  update: ScheduleUpdate,
): Promise<WorkerControl> {
  const dto = await callKnowledgeWorkerApi<WorkerControlDto>(actor, "POST", "/schedule", {
    enabled: update.enabled,
    interval_hours: update.intervalHours,
  });
  return toWorkerControl(dto);
}

export async function triggerWorkerRun(actor: ActorContext): Promise<WorkerControl> {
  const dto = await callKnowledgeWorkerApi<WorkerControlDto>(actor, "POST", "/trigger");
  return toWorkerControl(dto);
}
