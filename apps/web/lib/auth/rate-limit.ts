/**
 * Minimal fixed-window in-memory rate limiter for the login endpoint — a brute-force
 * speed bump, not a distributed limiter. In a multi-instance production deployment this is
 * the seam to back with Redis; the call sites stay identical.
 */

interface Window {
  count: number;
  resetAt: number;
}

const WINDOW_MS = 60_000;
const MAX_ATTEMPTS = 8;
const buckets = new Map<string, Window>();

export interface RateLimitResult {
  allowed: boolean;
  retryAfterSeconds: number;
}

export function checkRateLimit(key: string): RateLimitResult {
  const now = Date.now();
  const existing = buckets.get(key);
  if (!existing || now >= existing.resetAt) {
    buckets.set(key, { count: 1, resetAt: now + WINDOW_MS });
    return { allowed: true, retryAfterSeconds: 0 };
  }
  existing.count += 1;
  if (existing.count > MAX_ATTEMPTS) {
    return { allowed: false, retryAfterSeconds: Math.ceil((existing.resetAt - now) / 1000) };
  }
  return { allowed: true, retryAfterSeconds: 0 };
}

/** Clears a key's window after a successful login so legitimate users aren't penalized. */
export function resetRateLimit(key: string): void {
  buckets.delete(key);
}
