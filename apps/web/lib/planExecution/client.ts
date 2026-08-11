/** Browser-side Governance Plan API client — calls this app's own `/api/governance-plans/*`
 * routes (ADR 0066 §5, Phase 4). Mirrors `lib/risk/client.ts`'s shape. */

import type { CurrentMaturity, GovernancePlan, PlanDetail, PlanEvent, PlanItem } from "./types";

/**
 * A failed plan call, carrying the status the API actually answered.
 *
 * The status is not decoration: it decides what the user is told. "Someone else changed this item"
 * is only ever true of a `409`, and saying it after a `502` sends a person hunting for an edit
 * nobody made — which is exactly what happened while an optimistic-lock bug made every transition
 * answer 409.
 */
export class PlanActionError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code?: string,
  ) {
    super(message);
    this.name = "PlanActionError";
  }
}

async function toError(response: Response): Promise<PlanActionError> {
  const data = (await response.json().catch(() => ({}))) as { error?: string; code?: string };
  return new PlanActionError(
    response.status,
    data.error ?? `Request failed (${response.status}).`,
    data.code,
  );
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw await toError(response);
  return (await response.json()) as T;
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw await toError(response);
  return (await response.json()) as T;
}

export function fetchActivePlan(): Promise<PlanDetail | null> {
  return getJson<PlanDetail | null>("/api/governance-plans/active");
}

export function fetchPlanVersions(): Promise<GovernancePlan[]> {
  return getJson<{ items: GovernancePlan[] }>("/api/governance-plans/versions").then((r) => r.items);
}

export function fetchCurrentMaturity(): Promise<CurrentMaturity> {
  return getJson<CurrentMaturity>("/api/governance-plans/maturity");
}

export function fetchPlanItemEvents(itemId: string): Promise<PlanEvent[]> {
  return getJson<{ items: PlanEvent[] }>(
    `/api/governance-plans/items/${encodeURIComponent(itemId)}/events`,
  ).then((r) => r.items);
}

export function startPlanItem(itemId: string): Promise<PlanItem> {
  return postJson<PlanItem>(`/api/governance-plans/items/${encodeURIComponent(itemId)}/start`);
}

export function completePlanItem(itemId: string): Promise<PlanItem> {
  return postJson<PlanItem>(`/api/governance-plans/items/${encodeURIComponent(itemId)}/complete`);
}

export function reopenPlanItem(itemId: string): Promise<PlanItem> {
  return postJson<PlanItem>(`/api/governance-plans/items/${encodeURIComponent(itemId)}/reopen`);
}

export function attachPlanItemEvidence(itemId: string, evidenceIds: string[]): Promise<PlanItem> {
  return postJson<PlanItem>(`/api/governance-plans/items/${encodeURIComponent(itemId)}/evidence`, {
    evidenceIds,
  });
}
