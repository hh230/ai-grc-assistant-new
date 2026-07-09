/**
 * Database-backed fixed-window rate limiter (`rate_limit_buckets`, see
 * lib/db/migrations/0026_rate_limits.sql). Replaces the previous process-local in-memory
 * `Map`, which gave every serverless instance its own independent counter — no real
 * protection on Vercel's multi-instance model, and it reset on every redeploy/cold start.
 * A single atomic `INSERT ... ON CONFLICT DO UPDATE` both increments the counter and rolls
 * the window over, so concurrent requests across instances can't race past the limit.
 */

import { getPool } from "@/lib/db/pool";

const DEFAULT_WINDOW_MS = 60_000;
const DEFAULT_MAX_ATTEMPTS = 8;

export interface RateLimitResult {
  allowed: boolean;
  retryAfterSeconds: number;
}

export interface RateLimitOptions {
  windowMs?: number;
  maxAttempts?: number;
}

/**
 * Atomically increments `key`'s counter, rolling the window over if it has expired.
 * `allowed` is false once the count exceeds `maxAttempts` within the current window.
 */
export async function checkRateLimit(
  key: string,
  options: RateLimitOptions = {},
): Promise<RateLimitResult> {
  const windowMs = options.windowMs ?? DEFAULT_WINDOW_MS;
  const maxAttempts = options.maxAttempts ?? DEFAULT_MAX_ATTEMPTS;
  const now = new Date();
  const newResetAt = new Date(now.getTime() + windowMs);

  const { rows } = await getPool().query<{ count: number; reset_at: Date }>(
    `INSERT INTO rate_limit_buckets (bucket_key, count, reset_at)
     VALUES ($1, 1, $2)
     ON CONFLICT (bucket_key) DO UPDATE SET
       count = CASE WHEN rate_limit_buckets.reset_at <= $3 THEN 1
                    ELSE rate_limit_buckets.count + 1 END,
       reset_at = CASE WHEN rate_limit_buckets.reset_at <= $3 THEN $2
                       ELSE rate_limit_buckets.reset_at END
     RETURNING count, reset_at`,
    [key, newResetAt.toISOString(), now.toISOString()],
  );
  const row = rows[0]!;
  if (row.count > maxAttempts) {
    return {
      allowed: false,
      retryAfterSeconds: Math.max(0, Math.ceil((row.reset_at.getTime() - now.getTime()) / 1000)),
    };
  }
  return { allowed: true, retryAfterSeconds: 0 };
}

/** Clears a key's window (e.g. after a successful login) so legitimate users aren't
 * penalized by earlier failed attempts. */
export async function resetRateLimit(key: string): Promise<void> {
  await getPool().query(`DELETE FROM rate_limit_buckets WHERE bucket_key = $1`, [key]);
}
