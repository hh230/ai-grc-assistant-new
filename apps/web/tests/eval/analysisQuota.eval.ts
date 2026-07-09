/**
 * Integration check for the daily analysis quota's failure-accounting fix — no mocking,
 * exercises the real Postgres-backed `analyses` table and lib/analysis/usage.ts directly.
 * Verifies: a successful ("processed") analysis consumes quota, a failed one does not, and a
 * user whose only attempt today failed can still retry (their allowance isn't exhausted).
 *
 * Fabricates analysis rows directly via `analysisRepository.insert` rather than running the
 * real AI pipeline — this is a test of the *counting* logic in usage.ts, not of the pipeline
 * itself (that's covered by arabicAnalysis.eval.ts), so it stays fast and deterministic.
 *
 * Requires apps/web's live Postgres reachable via `DATABASE_URL` with migrations applied
 * (`npm run db:migrate`). Skips with a clear message rather than failing when it isn't set —
 * the same convention accessOnboarding.eval.ts uses.
 *
 * Run directly: `pnpm --filter @grc/web exec tsx tests/eval/analysisQuota.eval.ts`
 * Wired into `pnpm test` via package.json.
 */

import { randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import type { AnalysisRecord } from "../../lib/analysis/types";

// This file lives at apps/web/tests/eval/ — three levels below apps/web.
const appRoot = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
dotenv.config({ path: path.join(appRoot, ".env.local") });
dotenv.config({ path: path.join(appRoot, "..", "..", ".env") });

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(`FAIL: ${message}`);
}

async function assertThrows(fn: () => Promise<unknown>, message: string): Promise<void> {
  try {
    await fn();
  } catch {
    return;
  }
  throw new Error(`FAIL: ${message}`);
}

async function main(): Promise<void> {
  if (!process.env.DATABASE_URL) {
    console.log(
      "SKIP analysisQuota.eval — DATABASE_URL is not set (checked apps/web/.env.local and root .env).",
    );
    return;
  }

  const { getPool } = await import("../../lib/db/pool");
  const { analysisRepository } = await import("../../lib/analysis/repository");
  const {
    getDailyAnalysisUsage,
    assertDailyAnalysisAllowance,
    assertTenantDailyAnalysisAllowance,
    BETA_DAILY_ANALYSIS_LIMIT,
  } = await import("../../lib/analysis/usage");

  const runId = randomUUID().slice(0, 8);
  const userId = `e2e-quota-user-${runId}`;
  const tenantId = `e2e-quota-tenant-${runId}`;

  function makeRecord(status: AnalysisRecord["status"], version: number): AnalysisRecord {
    const now = new Date().toISOString();
    return {
      id: randomUUID(),
      documentId: `e2e-quota-doc-${runId}`,
      tenantId,
      fileName: "quota-test.pdf",
      title: `quota-test.pdf · v${version}`,
      version,
      status,
      charCount: 0,
      chunkCount: 0,
      findings: [],
      criticalRisks: [],
      frameworks: [],
      gaps: [],
      keyTerms: [],
      strengths: [],
      weaknesses: [],
      recommendations: [],
      references: [],
      nextActions: [],
      requestedByUserId: userId,
      requestedByName: "E2E Quota Tester",
      createdAt: now,
      updatedAt: now,
    };
  }

  try {
    // 1. A successful analysis increments the quota.
    await analysisRepository.insert(makeRecord("processed", 1));
    let usage = await getDailyAnalysisUsage(userId);
    assert(usage.used === 1, `expected used=1 after one processed analysis, got ${usage.used}`);
    assert(
      usage.remaining === BETA_DAILY_ANALYSIS_LIMIT - 1,
      `expected remaining=${BETA_DAILY_ANALYSIS_LIMIT - 1}, got ${usage.remaining}`,
    );

    // 2. A failed analysis does NOT increment the quota.
    await analysisRepository.insert(makeRecord("failed", 2));
    usage = await getDailyAnalysisUsage(userId);
    assert(
      usage.used === 1,
      `a failed analysis must not consume quota — expected used to stay 1, got ${usage.used}`,
    );

    // 3. Retry after failure is still allowed: with only 1 of 3 daily slots actually spent
    // (the failed one doesn't count), the allowance check must not throw.
    await assertDailyAnalysisAllowance(userId);
    await assertTenantDailyAnalysisAllowance(tenantId);

    // Fill the remaining real quota with processed runs and confirm the limit still bites —
    // the fix must not accidentally make the quota unenforceable.
    await analysisRepository.insert(makeRecord("processed", 3));
    await analysisRepository.insert(makeRecord("processed", 4));
    usage = await getDailyAnalysisUsage(userId);
    assert(
      usage.used === BETA_DAILY_ANALYSIS_LIMIT,
      `expected used=${BETA_DAILY_ANALYSIS_LIMIT} once fully spent, got ${usage.used}`,
    );
    await assertThrows(
      () => assertDailyAnalysisAllowance(userId),
      "the daily limit must still be enforced once genuinely exhausted by successful analyses",
    );

    // A failed attempt on top of an already-exhausted quota must not change anything (it
    // doesn't grant extra slots, and it doesn't count against the ones already spent).
    await analysisRepository.insert(makeRecord("failed", 5));
    usage = await getDailyAnalysisUsage(userId);
    assert(
      usage.used === BETA_DAILY_ANALYSIS_LIMIT,
      `a failed analysis at the cap must not change the used count, got ${usage.used}`,
    );

    console.log("PASS analysisQuota.eval — all checks passed.");
  } finally {
    const pool = getPool();
    await pool.query(`DELETE FROM analyses WHERE requested_by_user_id = $1`, [userId]);
    await pool.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
