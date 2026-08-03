/**
 * Forgot/reset password lifecycle (post-v2.0.1 audit): request a one-time reset link by
 * email, preview it on the reset-password page, and consume it to set a new password.
 * Mirrors `lib/invitations/service.ts`'s shape closely — same one-time-token discipline,
 * same row-locked transaction to defeat concurrent double-use. Node-only.
 */

import { randomUUID } from "node:crypto";
import { z } from "zod";
import { getPool } from "@/lib/db/pool";
import { hashPassword } from "@/lib/auth/password";
import { sendPasswordResetEmail } from "@/lib/email";
import { NotFoundError, ValidationError } from "@/lib/errors";
import { usersRepository } from "@/lib/users/repository";
import { passwordResetRepository } from "./repository";
import { generateResetToken, hashResetToken } from "./token";

const RESET_TTL_MINUTES = 60;

/**
 * Requests a reset link for `email`. Never throws and never reveals whether the address has
 * an account (CLAUDE.md §22 — treat auth failures uniformly to avoid user enumeration): the
 * route handler returns the same generic message either way. A no-op for unknown emails.
 */
export async function requestPasswordReset(email: string, baseUrl: string): Promise<void> {
  const user = await usersRepository.findByEmail(email);
  if (!user) return;

  const now = new Date();
  await passwordResetRepository.invalidateAllForUser(user.id, now.toISOString());

  const token = generateResetToken();
  const expiresAt = new Date(now.getTime() + RESET_TTL_MINUTES * 60 * 1000);
  await passwordResetRepository.create({
    id: randomUUID(),
    userId: user.id,
    tokenHash: hashResetToken(token),
    expiresAt: expiresAt.toISOString(),
    usedAt: null,
    createdAt: now.toISOString(),
  });

  const resetLink = new URL(
    `/reset-password?token=${encodeURIComponent(token)}`,
    baseUrl,
  ).toString();
  await sendPasswordResetEmail(user.email, { name: user.name, resetLink });
}

async function loadValidToken(token: string) {
  const record = await passwordResetRepository.findByTokenHash(hashResetToken(token));
  if (!record) throw new NotFoundError("This password reset link is invalid.");
  if (record.usedAt) {
    throw new ValidationError("This password reset link has already been used.");
  }
  if (new Date(record.expiresAt).getTime() < Date.now()) {
    throw new ValidationError("This password reset link has expired.");
  }
  return record;
}

export interface ResetTokenPreview {
  email: string;
}

/** Public-safe preview for the reset-password page — confirms the link is still usable and
 * shows which account it belongs to, without exposing the token hash. */
export async function previewResetToken(token: string): Promise<ResetTokenPreview> {
  const record = await loadValidToken(token);
  const user = await usersRepository.findById(record.userId);
  if (!user) throw new NotFoundError("This password reset link is invalid.");
  return { email: user.email };
}

export const resetPasswordSchema = z.object({
  password: z.string().min(10, "Password must be at least 10 characters.").max(256),
});

/** Consumes a reset token: validates it, sets the new password, and invalidates every other
 * outstanding token for the account — all under a row lock (`FOR UPDATE`) so two requests
 * racing on the same token cannot both succeed (CLAUDE.md §9, idempotent/retry-safe
 * consequential actions; mirrors `lib/invitations/service.ts#acceptInvitation`). */
export async function resetPassword(token: string, input: unknown): Promise<void> {
  const parsed = resetPasswordSchema.safeParse(input);
  if (!parsed.success) {
    throw new ValidationError(parsed.error.issues[0]?.message ?? "Invalid password.");
  }

  const record = await loadValidToken(token);
  const passwordHash = await hashPassword(parsed.data.password);
  const now = new Date().toISOString();

  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    const { rows: lockRows } = await client.query(
      `SELECT used_at FROM password_reset_tokens WHERE token_hash = $1 FOR UPDATE`,
      [record.tokenHash],
    );
    if (!lockRows[0] || lockRows[0].used_at) {
      throw new ValidationError("This password reset link has already been used.");
    }

    await client.query(`UPDATE users SET password_hash = $2 WHERE id = $1`, [
      record.userId,
      passwordHash,
    ]);
    await client.query(
      `UPDATE password_reset_tokens SET used_at = $2 WHERE user_id = $1 AND used_at IS NULL`,
      [record.userId, now],
    );
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
