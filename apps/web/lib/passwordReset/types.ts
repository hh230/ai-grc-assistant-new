/** Forgot/reset password (post-v2.0.1 audit). A token is a one-time, expiring credential
 * scoped to an existing user account — mirrors `lib/invitations/types.ts`'s `Invitation`. */
export interface PasswordResetToken {
  id: string;
  userId: string;
  /** sha256 hex of the raw token — never the raw token itself. */
  tokenHash: string;
  expiresAt: string;
  usedAt: string | null;
  createdAt: string;
}
