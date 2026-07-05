/** Browser-side Policy Intelligence API client — calls this app's own proxy routes under
 * `/api/policy-intelligence/*`, never `apps/api` directly (CLAUDE.md: the frontend never
 * talks to a backend service's credentials; the server-side route handler holds those). */

import type { CoverageGapScan, ObligationEvidence, PolicyQualityReview } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

function withControlDomain(path: string, controlDomain?: string): string {
  if (!controlDomain) return path;
  return `${path}?controlDomain=${encodeURIComponent(controlDomain)}`;
}

export async function fetchObligations(controlDomain?: string): Promise<ObligationEvidence[]> {
  const response = await fetch(
    withControlDomain("/api/policy-intelligence/obligations", controlDomain),
    { cache: "no-store" },
  );
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { obligations: ObligationEvidence[] }).obligations;
}

export async function fetchCoverageGaps(controlDomain?: string): Promise<CoverageGapScan> {
  const response = await fetch(
    withControlDomain("/api/policy-intelligence/coverage-gaps", controlDomain),
    { cache: "no-store" },
  );
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as CoverageGapScan;
}

export async function fetchPolicyQualityReview(policyId: string): Promise<PolicyQualityReview> {
  const response = await fetch(
    `/api/policy-intelligence/policies/${encodeURIComponent(policyId)}/quality-review`,
    { cache: "no-store" },
  );
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as PolicyQualityReview;
}
