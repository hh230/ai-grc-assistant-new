/** Browser-side AI Worker Control Center API client — calls this app's own proxy routes
 * under `/api/knowledge-worker/*`, never `apps/api` directly (CLAUDE.md: the frontend never
 * holds backend credentials; the server-side route handler holds those). */

import type {
  LearningReports,
  ScheduleUpdate,
  WorkerControl,
  WorkerEvent,
  WorkerRun,
  WorkerStatus,
} from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export async function fetchWorkerStatus(): Promise<WorkerStatus> {
  const response = await fetch("/api/knowledge-worker/status", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as WorkerStatus;
}

export async function fetchWorkerEvents(limit = 50): Promise<WorkerEvent[]> {
  const response = await fetch(`/api/knowledge-worker/events?limit=${limit}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { events: WorkerEvent[] }).events;
}

export async function fetchWorkerRuns(limit = 20): Promise<WorkerRun[]> {
  const response = await fetch(`/api/knowledge-worker/runs?limit=${limit}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { runs: WorkerRun[] }).runs;
}

export async function fetchLearningReports(): Promise<LearningReports> {
  const response = await fetch("/api/knowledge-worker/reports", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as LearningReports;
}

export async function updateSchedule(update: ScheduleUpdate): Promise<WorkerControl> {
  const response = await fetch("/api/knowledge-worker/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as WorkerControl;
}

export async function triggerRun(): Promise<WorkerControl> {
  const response = await fetch("/api/knowledge-worker/trigger", { method: "POST" });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as WorkerControl;
}
