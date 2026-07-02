/** Browser-side risk API client. */

import type { Risk, RiskStatus, RiskSummary } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export async function fetchRisks(): Promise<RiskSummary[]> {
  const response = await fetch("/api/risks", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { risks: RiskSummary[] }).risks;
}

export async function fetchRisk(id: string): Promise<Risk> {
  const response = await fetch(`/api/risks/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { risk: Risk }).risk;
}

export interface RiskInput {
  title: string;
  description?: string;
  category?: string;
  likelihood?: number;
  impact?: number;
  ownerName?: string;
  controlIds?: string[];
  mitigationPlan?: string;
  residualLikelihood?: number | null;
  residualImpact?: number | null;
}

export async function createRisk(input: RiskInput): Promise<Risk> {
  const response = await fetch("/api/risks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { risk: Risk }).risk;
}

export async function updateRisk(id: string, patch: Partial<RiskInput>): Promise<Risk> {
  const response = await fetch(`/api/risks/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { risk: Risk }).risk;
}

export async function transitionRisk(id: string, status: RiskStatus): Promise<Risk> {
  const response = await fetch(`/api/risks/${id}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { risk: Risk }).risk;
}

export async function deleteRisk(id: string): Promise<void> {
  const response = await fetch(`/api/risks/${id}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await parseError(response));
}
