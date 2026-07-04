/** Browser-side organizations API client. */

import type { OrganizationMembership } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export interface MyOrganizations {
  organizations: OrganizationMembership[];
  activeOrganizationId: string;
}

export async function fetchMyOrganizations(): Promise<MyOrganizations> {
  const response = await fetch("/api/organizations", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as MyOrganizations;
}

export interface CreateOrganizationInput {
  name: string;
  orgType: string;
  industry: string;
}

export async function createOrganization(input: CreateOrganizationInput): Promise<void> {
  const response = await fetch("/api/organizations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await parseError(response));
}

export async function switchOrganization(organizationId: string): Promise<void> {
  const response = await fetch("/api/organizations/switch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ organizationId }),
  });
  if (!response.ok) throw new Error(await parseError(response));
}
