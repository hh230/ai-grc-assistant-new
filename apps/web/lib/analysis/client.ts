/** Browser-side analysis API client. */

import type { AnalysisRecord, AnalysisUsage } from "./types";
import type { AnalysisWithVersionCount } from "./repository";

/** An API error that preserves the server's stable error `code` (e.g. `beta_daily_limit`)
 *  so callers can branch on it — a bare `Error` would lose it in its message. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  const data = (await response.json().catch(() => ({}))) as { error?: string; code?: string };
  return new ApiError(data.error ?? `Request failed (${response.status}).`, data.code);
}

/** Latest version per document — the analysis history list. */
export async function fetchAnalyses(): Promise<AnalysisWithVersionCount[]> {
  const response = await fetch("/api/analyses", { cache: "no-store" });
  if (!response.ok) throw await toApiError(response);
  return ((await response.json()) as { analyses: AnalysisWithVersionCount[] }).analyses;
}

/** Every version for a document, newest first. `versions[0]` is the latest, if any exist. */
export async function fetchAnalysisVersions(documentId: string): Promise<AnalysisRecord[]> {
  const response = await fetch(`/api/documents/${documentId}/analyses`, { cache: "no-store" });
  if (!response.ok) throw await toApiError(response);
  return ((await response.json()) as { versions: AnalysisRecord[] }).versions;
}

/** One specific analysis version by its own id. */
export async function fetchAnalysis(analysisId: string): Promise<AnalysisRecord | null> {
  const response = await fetch(`/api/analyses/${analysisId}`, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw await toApiError(response);
  return ((await response.json()) as { analysis: AnalysisRecord }).analysis;
}

export async function startAnalysis(documentId: string): Promise<AnalysisRecord> {
  const response = await fetch(`/api/documents/${documentId}/analyze`, { method: "POST" });
  if (!response.ok) throw await toApiError(response);
  return ((await response.json()) as { analysis: AnalysisRecord }).analysis;
}

export async function renameAnalysis(analysisId: string, title: string): Promise<AnalysisRecord> {
  const response = await fetch(`/api/analyses/${analysisId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw await toApiError(response);
  return ((await response.json()) as { analysis: AnalysisRecord }).analysis;
}

export async function deleteAnalysis(analysisId: string): Promise<void> {
  const response = await fetch(`/api/analyses/${analysisId}`, { method: "DELETE" });
  if (!response.ok) throw await toApiError(response);
}

/** The current user's remaining beta analysis budget for today. */
export async function fetchAnalysisUsage(): Promise<AnalysisUsage> {
  const response = await fetch("/api/analyses/usage", { cache: "no-store" });
  if (!response.ok) throw await toApiError(response);
  return ((await response.json()) as { usage: AnalysisUsage }).usage;
}
