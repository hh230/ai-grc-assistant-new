/** Browser-side Invitations API client — calls this app's own routes under
 * `/api/invitations/[token]/*` (KI-P9, ADR-0034). */

import type { InvitedRole } from "./types";

async function parseError(response: Response): Promise<string> {
  const data = (await response.json().catch(() => ({}))) as { error?: string };
  return data.error ?? `Request failed (${response.status}).`;
}

export interface InvitationPreviewDto {
  email: string;
  organizationName: string;
  invitedRole: InvitedRole;
  expiresAt: string;
}

export async function fetchInvitationPreview(token: string): Promise<InvitationPreviewDto> {
  const response = await fetch(`/api/invitations/${encodeURIComponent(token)}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as { invitation: InvitationPreviewDto }).invitation;
}

export async function acceptInvitation(
  token: string,
  input: { name: string; password: string },
): Promise<void> {
  const response = await fetch(`/api/invitations/${encodeURIComponent(token)}/accept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await parseError(response));
}
