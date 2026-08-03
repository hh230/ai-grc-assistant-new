/**
 * Password-reset token repository, backed by PostgreSQL (`password_reset_tokens`,
 * 0029_password_resets.sql). Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type { PasswordResetToken } from "./types";

export interface PasswordResetRepository {
  create(token: PasswordResetToken): Promise<PasswordResetToken>;
  findByTokenHash(tokenHash: string): Promise<PasswordResetToken | null>;
  /** Marks every outstanding (unused) token for a user consumed, without a "used_at" that
   * implies a successful reset — used both when a new token is requested (so only the latest
   * link works) and after a successful reset (so no other in-flight link remains valid). */
  invalidateAllForUser(userId: string, invalidatedAt: string): Promise<void>;
}

interface PasswordResetRow {
  id: string;
  user_id: string;
  token_hash: string;
  expires_at: Date;
  used_at: Date | null;
  created_at: Date;
}

function toToken(row: PasswordResetRow): PasswordResetToken {
  return {
    id: row.id,
    userId: row.user_id,
    tokenHash: row.token_hash,
    expiresAt: row.expires_at.toISOString(),
    usedAt: row.used_at ? row.used_at.toISOString() : null,
    createdAt: row.created_at.toISOString(),
  };
}

class PostgresPasswordResetRepository implements PasswordResetRepository {
  async create(token: PasswordResetToken): Promise<PasswordResetToken> {
    await getPool().query(
      `INSERT INTO password_reset_tokens (id, user_id, token_hash, expires_at, used_at, created_at)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [token.id, token.userId, token.tokenHash, token.expiresAt, token.usedAt, token.createdAt],
    );
    return token;
  }

  async findByTokenHash(tokenHash: string): Promise<PasswordResetToken | null> {
    const { rows } = await getPool().query<PasswordResetRow>(
      `SELECT * FROM password_reset_tokens WHERE token_hash = $1`,
      [tokenHash],
    );
    return rows[0] ? toToken(rows[0]) : null;
  }

  async invalidateAllForUser(userId: string, invalidatedAt: string): Promise<void> {
    await getPool().query(
      `UPDATE password_reset_tokens SET used_at = $2
        WHERE user_id = $1 AND used_at IS NULL`,
      [userId, invalidatedAt],
    );
  }
}

export const passwordResetRepository: PasswordResetRepository =
  new PostgresPasswordResetRepository();
