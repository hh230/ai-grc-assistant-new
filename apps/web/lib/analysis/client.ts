/** Browser-side analysis API client. */

import type { AnalysisRecord } from "./types";
import type { AnalysisWithVersionCount } from "./repository";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

/** Latest version per document — the analysis history list. */
export async function fetchAnalyses(): Promise<AnalysisWithVersionCount[]> {
  const response = await fetch("/api/analyses", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { analyses: AnalysisWithVersionCount[] }).analyses;
}

/** Every version for a document, newest first. `versions[0]` is the latest, if any exist. */
export async function fetchAnalysisVersions(documentId: string): Promise<AnalysisRecord[]> {
  const response = await fetch(`/api/documents/${documentId}/analyses`, { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { versions: AnalysisRecord[] }).versions;
}

/** One specific analysis version by its own id. */
export async function fetchAnalysis(analysisId: string): Promise<AnalysisRecord | null> {
  const response = await fetch(`/api/analyses/${analysisId}`, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { analysis: AnalysisRecord }).analysis;
}

export async function startAnalysis(documentId: string): Promise<AnalysisRecord> {
  const response = await fetch(`/api/documents/${documentId}/analyze`, { method: "POST" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { analysis: AnalysisRecord }).analysis;
}

export async function renameAnalysis(analysisId: string, title: string): Promise<AnalysisRecord> {
  const response = await fetch(`/api/analyses/${analysisId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { analysis: AnalysisRecord }).analysis;
}

export async function deleteAnalysis(analysisId: string): Promise<void> {
  const response = await fetch(`/api/analyses/${analysisId}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await parseError(response));
}
