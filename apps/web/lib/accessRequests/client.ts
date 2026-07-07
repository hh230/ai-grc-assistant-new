/** Browser-side Access Requests API client — calls this app's own routes under
 * `/api/access-requests/*` (KI-P9, ADR-0034). Mirrors `lib/regulationReview/client.ts`. */

import type { InvitedRole } from "@/lib/invitations/types";
import type { AccessRequest } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export interface SubmitAccessRequestInput {
  name: string;
  email: string;
  organizationName: string;
  roleTitle: string;
  message?: string;
}

export async function submitAccessRequest(input: SubmitAccessRequestInput): Promise<AccessRequest> {
  const response = await fetch("/api/access-requests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { accessRequest: AccessRequest }).accessRequest;
}

export async function fetchAccessRequests(): Promise<AccessRequest[]> {
  const response = await fetch("/api/access-requests", { cache: "no-store" });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { requests: AccessRequest[] }).requests;
}

export interface ApproveAccessRequestResponse {
  accessRequest: AccessRequest;
  inviteLink: string;
  expiresAt: string;
}

export async function approveAccessRequest(
  id: string,
  invitedRole: InvitedRole,
): Promise<ApproveAccessRequestResponse> {
  const response = await fetch(`/api/access-requests/${encodeURIComponent(id)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ invitedRole }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as ApproveAccessRequestResponse;
}

export async function rejectAccessRequest(id: string): Promise<AccessRequest> {
  const response = await fetch(`/api/access-requests/${encodeURIComponent(id)}/reject`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { accessRequest: AccessRequest }).accessRequest;
}
