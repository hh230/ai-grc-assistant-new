/** Browser-side client for the customer's sector stage (ADR 0067). */

import type { SectorAnswer, SectorInterview } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export async function openSectorInterview(sessionId: string): Promise<SectorInterview> {
  const response = await fetch(`/api/sector-interview/${sessionId}`, { method: "POST" });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as SectorInterview;
}

export async function findOpenSectorInterview(): Promise<SectorInterview> {
  const response = await fetch("/api/sector-interview/open", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as SectorInterview;
}

/**
 * Saves ONE answer, the moment it is given. Separate from `submitSectorAnswers` because it means
 * something different: this records an answer, that concludes an interview.
 */
export async function saveSectorAnswer(
  assessmentId: string,
  answer: SectorAnswer,
): Promise<void> {
  const response = await fetch(`/api/sector-interview/assessments/${assessmentId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers: [answer] }),
  });
  if (!response.ok) throw new Error(await parseError(response));
}

export async function submitSectorAnswers(
  assessmentId: string,
  answers: SectorAnswer[],
): Promise<void> {
  const response = await fetch(`/api/sector-interview/assessments/${assessmentId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  if (!response.ok) throw new Error(await parseError(response));
}
