/**
 * Integration check: the Policy Intelligence proxy (`lib/policyIntelligence/service.ts`)
 * actually reaches `apps/api`'s real Policy Hunter/Analyst endpoints (PI-P5, ADR-0022) and
 * shapes their response correctly — no mocking, since the one thing worth regression-testing
 * here is the real cross-service call (auth header, URL, snake_case→camelCase translation,
 * error mapping), not business logic that already has its own test suite in `apps/api`.
 *
 * Requires `apps/api` reachable at `NEXT_PUBLIC_API_BASE_URL` (default
 * `http://localhost:8000`) with `API_AUTH_TOKENS` seeded for `dev-token`/`dev-org` (the same
 * dev principal `apps/api/.../composition.py` seeds), and apps/web's live Postgres reachable
 * from it. Skips with a clear message rather than failing when apps/api isn't running — the
 * same convention `arabicAnalysis.eval.ts` uses for a missing `OPENAI_API_KEY`.
 *
 * Run directly: `pnpm --filter @grc/web exec tsx tests/eval/policyIntelligence.eval.ts`
 * Wired into `pnpm test` via package.json.
 */

import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import type { ActorContext } from "../../lib/auth/actor";

// This file lives at apps/web/tests/eval/ — three levels below apps/web.
const appRoot = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
dotenv.config({ path: path.join(appRoot, ".env.local") });
dotenv.config({ path: path.join(appRoot, "..", "..", ".env") });

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const DEV_ACTOR: ActorContext = {
  userId: "dev-user",
  userName: "Dev Owner",
  tenantId: "dev-org",
  roles: ["owner"],
  apiToken: "dev-token",
};

async function apiIsReachable(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/healthz`);
    return response.ok;
  } catch {
    return false;
  }
}

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(`FAIL: ${message}`);
}

async function main(): Promise<void> {
  if (!(await apiIsReachable())) {
    console.log(
      `SKIP policyIntelligence.eval — apps/api is not reachable at ${API_BASE_URL} ` +
        "(start it with `uv run uvicorn grc_api.app:create_app --factory` from the repo root).",
    );
    return;
  }

  const { listObligations, scanCoverageGaps, reviewPolicyQuality } = await import(
    "../../lib/policyIntelligence/service"
  );
  const { NotFoundError } = await import("../../lib/errors");

  const obligations = await listObligations(DEV_ACTOR);
  assert(Array.isArray(obligations), "listObligations should return an array");
  for (const obligation of obligations) {
    assert(typeof obligation.obligationId === "string", "obligationId should be a string");
    assert(typeof obligation.citation === "string" && obligation.citation.length > 0, "citation should be present");
  }
  console.log(`OK listObligations — ${obligations.length} confirmed obligations`);

  const scan = await scanCoverageGaps(DEV_ACTOR);
  assert(Array.isArray(scan.findings), "scanCoverageGaps.findings should be an array");
  assert(typeof scan.obligationsScanned === "number", "obligationsScanned should be a number");
  assert(typeof scan.policiesConsidered === "number", "policiesConsidered should be a number");
  console.log(
    `OK scanCoverageGaps — ${scan.obligationsScanned} scanned, ${scan.findings.length} gaps`,
  );

  let threw = false;
  try {
    await reviewPolicyQuality(DEV_ACTOR, "does-not-exist");
  } catch (error) {
    threw = error instanceof NotFoundError;
  }
  assert(threw, "reviewPolicyQuality should raise NotFoundError for an unknown policy id");
  console.log("OK reviewPolicyQuality — unknown policy id maps to NotFoundError");

  console.log("policyIntelligence.eval — all checks passed");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
