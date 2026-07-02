/** Browser-side policy API client. */

import type { Policy, PolicyStatus, PolicySummary } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export async function fetchPolicies(): Promise<PolicySummary[]> {
  const response = await fetch("/api/policies", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { policies: PolicySummary[] }).policies;
}

export async function fetchPolicy(id: string): Promise<Policy> {
  const response = await fetch(`/api/policies/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { policy: Policy }).policy;
}

export interface PolicyInput {
  title: string;
  summary?: string;
  body?: string;
  ownerName?: string;
  controlIds?: string[];
}

export async function createPolicy(input: PolicyInput): Promise<Policy> {
  const response = await fetch("/api/policies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { policy: Policy }).policy;
}

export async function updatePolicy(id: string, patch: Partial<PolicyInput>): Promise<Policy> {
  const response = await fetch(`/api/policies/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { policy: Policy }).policy;
}

export async function transitionPolicy(id: string, status: PolicyStatus): Promise<Policy> {
  const response = await fetch(`/api/policies/${id}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { policy: Policy }).policy;
}

export async function deletePolicy(id: string): Promise<void> {
  const response = await fetch(`/api/policies/${id}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await parseError(response));
}
