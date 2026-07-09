/**
 * Invitation lifecycle (KI-P9, ADR-0034): create a one-time token when an access request is
 * approved, preview it on the public accept-invite page, and accept it — which is also where
 * the invitee's brand-new organization is actually created (the invitation only ever stored
 * its *name*; see `lib/invitations/types.ts`). Node-only.
 */

import { randomUUID } from "node:crypto";
import { z } from "zod";
import { getPool } from "@/lib/db/pool";
import { hashPassword } from "@/lib/auth/password";
import type { UserRole } from "@/lib/auth/roles";
import { NotFoundError, ValidationError } from "@/lib/errors";
import { invitationRepository } from "./repository";
import { generateInviteToken, hashInviteToken } from "./token";
import { mapInvitedRoleToUserRole, type Invitation, type InvitedRole } from "./types";

const INVITE_TTL_DAYS = 7;

export interface CreateInvitationInput {
  email: string;
  organizationName: string;
  invitedRole: InvitedRole;
  accessRequestId?: string | null;
  /** Set only for a team invite — see `Invitation.organizationId`. */
  organizationId?: string | null;
}

export interface CreatedInvitation {
  invitation: Invitation;
  /** The raw, unhashed token — only ever available here, at creation time. */
  token: string;
}

export async function createInvitation(
  input: CreateInvitationInput,
): Promise<CreatedInvitation> {
  const token = generateInviteToken();
  const now = new Date();
  const expiresAt = new Date(now.getTime() + INVITE_TTL_DAYS * 24 * 60 * 60 * 1000);
  const invitation: Invitation = {
    id: randomUUID(),
    email: input.email.trim().toLowerCase(),
    organizationName: input.organizationName,
    invitedRole: input.invitedRole,
    tokenHash: hashInviteToken(token),
    expiresAt: expiresAt.toISOString(),
    usedAt: null,
    accessRequestId: input.accessRequestId ?? null,
    organizationId: input.organizationId ?? null,
    createdAt: now.toISOString(),
  };
  await invitationRepository.create(invitation);
  return { invitation, token };
}

export interface InvitationPreview {
  email: string;
  organizationName: string;
  invitedRole: InvitedRole;
  expiresAt: string;
}

async function loadValidInvitation(token: string): Promise<Invitation> {
  const invitation = await invitationRepository.findByTokenHash(hashInviteToken(token));
  if (!invitation) throw new NotFoundError("This invite link is invalid.");
  if (invitation.usedAt) throw new ValidationError("This invite link has already been used.");
  if (new Date(invitation.expiresAt).getTime() < Date.now()) {
    throw new ValidationError("This invite link has expired.");
  }
  return invitation;
}

/** Public-safe preview for the accept-invite page — never the token hash. */
export async function previewInvitation(token: string): Promise<InvitationPreview> {
  const invitation = await loadValidInvitation(token);
  return {
    email: invitation.email,
    organizationName: invitation.organizationName,
    invitedRole: invitation.invitedRole,
    expiresAt: invitation.expiresAt,
  };
}

export const acceptInvitationSchema = z.object({
  name: z.string().trim().min(1, "Your name is required.").max(200),
  password: z.string().min(10, "Password must be at least 10 characters.").max(256),
});

export interface AcceptedInvitation {
  userId: string;
  email: string;
  name: string;
  organizationId: string;
  organizationName: string;
  role: UserRole;
}

/** Creates the user (+ a new organization, unless this is a team invite for an existing one)
 * and marks the invitation used, all in one transaction with a row lock on the invitation
 * (`FOR UPDATE`) so two requests racing on the same token cannot both succeed — one-time use
 * is enforced under concurrency, not just by the earlier read in `loadValidInvitation`
 * (CLAUDE.md §9, idempotent/retry-safe consequential actions).
 *
 * Branches on `invitation.organizationId`: unset means the original KI-P9 flow (a brand-new
 * organization is created here); set means a team invite (lib/organizations/service.ts
 * #inviteTeamMember) — the user joins that existing organization and no new one is created. */
export async function acceptInvitation(
  token: string,
  input: unknown,
): Promise<AcceptedInvitation> {
  const parsed = acceptInvitationSchema.safeParse(input);
  if (!parsed.success) {
    throw new ValidationError(parsed.error.issues[0]?.message ?? "Invalid signup details.");
  }

  const invitation = await loadValidInvitation(token);
  const isTeamInvite = Boolean(invitation.organizationId);
  const passwordHash = await hashPassword(parsed.data.password);
  const userId = randomUUID();
  const organizationId = invitation.organizationId ?? randomUUID();
  const now = new Date().toISOString();
  const role = mapInvitedRoleToUserRole(invitation.invitedRole);

  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    const { rows: lockRows } = await client.query(
      `SELECT used_at FROM invitations WHERE token_hash = $1 FOR UPDATE`,
      [invitation.tokenHash],
    );
    if (!lockRows[0] || lockRows[0].used_at) {
      throw new ValidationError("This invite link has already been used.");
    }

    const { rows: existingUser } = await client.query(
      `SELECT id FROM users WHERE lower(email) = lower($1)`,
      [invitation.email],
    );
    if (existingUser.length > 0) {
      throw new ValidationError("An account with this email already exists.");
    }

    await client.query(
      `INSERT INTO users (id, email, name, password_hash, created_at)
       VALUES ($1, $2, $3, $4, $5)`,
      [userId, invitation.email, parsed.data.name, passwordHash, now],
    );
    if (!isTeamInvite) {
      await client.query(
        `INSERT INTO organizations (id, name, org_type, industry, created_by_user_id, created_at)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [organizationId, invitation.organizationName, "Unspecified", "Unspecified", userId, now],
      );
    }
    await client.query(
      `INSERT INTO user_organizations (user_id, organization_id, role) VALUES ($1, $2, $3)`,
      [userId, organizationId, role],
    );
    await client.query(`UPDATE invitations SET used_at = $2 WHERE id = $1`, [invitation.id, now]);
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }

  return {
    userId,
    email: invitation.email,
    name: parsed.data.name,
    organizationId,
    organizationName: invitation.organizationName,
    role,
  };
}
