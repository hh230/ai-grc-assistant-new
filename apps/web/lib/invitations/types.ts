/** Invite-based onboarding (KI-P9, ADR-0034). An invitation is a one-time, expiring
 * credential created only by approving an `AccessRequest`; the organization it names does not
 * exist yet — it is created at acceptance time (`service.ts#acceptInvitation`), which is why
 * this stores `organizationName`, not an `organizations.id` foreign key. */

import type { UserRole } from "@/lib/auth/roles";

/** The three roles offered on the admin approval form. Mapped to the platform's full
 * `UserRole` roster at acceptance time — see `mapInvitedRoleToUserRole` below. */
export const INVITED_ROLES = ["owner", "admin", "member"] as const;
export type InvitedRole = (typeof INVITED_ROLES)[number];

export interface Invitation {
  id: string;
  email: string;
  organizationName: string;
  invitedRole: InvitedRole;
  /** sha256 hex of the raw token — never the raw token itself. */
  tokenHash: string;
  expiresAt: string;
  usedAt: string | null;
  accessRequestId: string | null;
  createdAt: string;
}

/** The invitation is always for a brand-new organization with exactly one member so far, so
 * `owner`/`admin` both resolve to full tenant control either way (CLAUDE.md §21 permission
 * matrix grants both every action on every resource). `member` maps to `analyst` — a
 * contributor role that can author operational work but not approve, publish, or delete. */
export function mapInvitedRoleToUserRole(role: InvitedRole): UserRole {
  if (role === "member") return "analyst";
  return role;
}
