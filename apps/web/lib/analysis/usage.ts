/**
 * Beta usage limits — each authenticated user may start at most a fixed number of document
 * analyses per calendar day. Enforced server-side (see `startAnalysis` in ./service) and
 * surfaced to the UI via /api/analyses/usage.
 *
 * The count comes straight from the `analyses` table, filtered to `status <> 'failed'`: every
 * run inserts exactly one row stamped with `requested_by_user_id` and `created_at`, starting
 * as "processing". That row counts against the quota immediately — a *reservation* — so a
 * burst of concurrent requests can't all start before any of them resolve and blow past the
 * limit. If the run succeeds, the row becomes "processed" and the slot is permanently spent.
 * If it fails (AI provider error, timeout, infrastructure failure — anything `markFailed` in
 * ./service handles), the row becomes "failed" and drops out of the count on the very next
 * check, releasing the reservation so the user can immediately retry. Scoped by user id, not
 * tenant or browser session, so switching organizations does not reset the budget.
 * Node-only (reads the DB pool).
 */

import { getPool } from "@/lib/db/pool";
import { RateLimitError } from "@/lib/errors";
import { BETA_DAILY_LIMIT_CODE, TENANT_DAILY_LIMIT_CODE, type AnalysisUsage } from "./types";

/** Beta allowance: document analyses a single user may start per day. */
export const BETA_DAILY_ANALYSIS_LIMIT = 3;

/** Tenant-wide allowance: document analyses an entire organization may start per day,
 * regardless of how many users it has — caps aggregate cost/load per tenant on top of the
 * per-user limit above. Deliberately not a multiple of the per-user limit: adding more users
 * to an org does not grant more org-wide quota (3 users each getting their own 3/day would
 * already exceed this on day one), so this is a real, independent cap, not just "seats × 3". */
export const TENANT_DAILY_ANALYSIS_LIMIT = 10;

/**
 * Timezone the daily window is anchored to. The product is KSA-first (NCA ECC, SAMA, PDPL),
 * so "today" and "tomorrow" mean the user's calendar day in Riyadh — not the server's UTC
 * day. Riyadh has no DST, so day boundaries are stable year-round.
 */
const USAGE_TIME_ZONE = "Asia/Riyadh";
const DAY_MS = 24 * 60 * 60 * 1000;

/** Offset (target zone minus UTC) in ms at the given instant, via wall-clock reconstruction. */
function timeZoneOffsetMs(instant: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(instant);
  const field = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  const wallAsUtc = Date.UTC(
    field("year"),
    field("month") - 1,
    field("day"),
    field("hour"),
    field("minute"),
    field("second"),
  );
  return wallAsUtc - instant.getTime();
}

/** The instant of the most recent midnight in `USAGE_TIME_ZONE` at or before `now`. */
function startOfUsageDay(now: Date): Date {
  const ymd = new Intl.DateTimeFormat("en-CA", {
    timeZone: USAGE_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now); // e.g. "2026-07-08"
  const wallMidnightUtc = new Date(`${ymd}T00:00:00Z`).getTime();
  return new Date(wallMidnightUtc - timeZoneOffsetMs(now, USAGE_TIME_ZONE));
}

/** How many analyses this user has started today (excluding failed runs — see the module
 * docstring), and how many they have left. */
export async function getDailyAnalysisUsage(
  userId: string,
  now: Date = new Date(),
): Promise<AnalysisUsage> {
  const dayStart = startOfUsageDay(now);
  const { rows } = await getPool().query<{ used: string }>(
    `SELECT count(*)::text AS used
       FROM analyses
      WHERE requested_by_user_id = $1
        AND created_at >= $2
        AND status <> 'failed'`,
    [userId, dayStart.toISOString()],
  );
  const used = Number(rows[0]?.used ?? 0);
  const remaining = Math.max(0, BETA_DAILY_ANALYSIS_LIMIT - used);
  return {
    limit: BETA_DAILY_ANALYSIS_LIMIT,
    used,
    remaining,
    resetsAt: new Date(dayStart.getTime() + DAY_MS).toISOString(),
  };
}

/**
 * Throw a 429 `RateLimitError` (code {@link BETA_DAILY_LIMIT_CODE}) if the user has no
 * analyses left today. Call this before doing any consequential work in `startAnalysis`.
 */
export async function assertDailyAnalysisAllowance(userId: string): Promise<AnalysisUsage> {
  const usage = await getDailyAnalysisUsage(userId);
  if (usage.remaining <= 0) {
    throw new RateLimitError(
      `Daily beta analysis limit reached (${usage.limit} documents).`,
      BETA_DAILY_LIMIT_CODE,
    );
  }
  return usage;
}

/** How many analyses this tenant (across all its users) has started today, excluding failed
 * runs — same reservation semantics as the per-user count above. */
async function getTenantDailyAnalysisUsage(tenantId: string, now: Date = new Date()) {
  const dayStart = startOfUsageDay(now);
  const { rows } = await getPool().query<{ used: string }>(
    `SELECT count(*)::text AS used
       FROM analyses
      WHERE tenant_id = $1
        AND created_at >= $2
        AND status <> 'failed'`,
    [tenantId, dayStart.toISOString()],
  );
  return Number(rows[0]?.used ?? 0);
}

/** Throw a 429 `RateLimitError` (code {@link TENANT_DAILY_LIMIT_CODE}) if this tenant, across
 * all of its users, has no analyses left today. Complements the per-user gate above — caps
 * aggregate load even if no single user has hit their own limit. */
export async function assertTenantDailyAnalysisAllowance(tenantId: string): Promise<void> {
  const used = await getTenantDailyAnalysisUsage(tenantId);
  if (used >= TENANT_DAILY_ANALYSIS_LIMIT) {
    throw new RateLimitError(
      `This organization's daily analysis limit has been reached (${TENANT_DAILY_ANALYSIS_LIMIT} documents).`,
      TENANT_DAILY_LIMIT_CODE,
    );
  }
}
