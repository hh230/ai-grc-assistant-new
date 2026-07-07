/** Browser-side Regulation Review API client — calls this app's own proxy routes under
 * `/api/regulation-review/*`, never `apps/api` directly (CLAUDE.md: the frontend never holds
 * backend credentials; the server-side route handler holds those). */

import type {
  ApproveRegulationResult,
  PendingRegulationVersion,
  RegulationVersionDetail,
  RejectRegulationResult,
} from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export async function fetchPendingRegulationVersions(): Promise<PendingRegulationVersion[]> {
  const response = await fetch("/api/regulation-review/pending", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { versions: PendingRegulationVersion[] }).versions;
}

export async function fetchRegulationVersionDetail(
  versionId: string,
): Promise<RegulationVersionDetail> {
  const response = await fetch(`/api/regulation-review/${encodeURIComponent(versionId)}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as RegulationVersionDetail;
}

export async function approveRegulationVersion(
  versionId: string,
): Promise<ApproveRegulationResult> {
  const response = await fetch(
    `/api/regulation-review/${encodeURIComponent(versionId)}/approve`,
    { method: "POST" },
  );
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as ApproveRegulationResult;
}

export async function rejectRegulationVersion(versionId: string): Promise<RejectRegulationResult> {
  const response = await fetch(`/api/regulation-review/${encodeURIComponent(versionId)}/reject`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as RejectRegulationResult;
}
