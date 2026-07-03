/**
 * Regression check: an Arabic-locale document assessment must return its narrative content
 * in Arabic, not English (CLAUDE.md §22 — "AI components get evaluation tests ... accuracy
 * and grounding are regression-tested"). Exercises the real prompt + real model + real
 * schema validation — no mocking, since the failure mode this guards against is the model
 * itself drifting to English despite the language directive (a `response_format:
 * json_object` reliability gap, not a bug a mocked LLM could ever catch).
 *
 * Requires a live `OPENAI_API_KEY` (reads the same `.env.local` / root `.env` as the app) —
 * skips with a clear message rather than failing when no provider is configured, so `pnpm
 * test` stays green in environments without secrets (e.g. a sandboxed CI runner).
 *
 * Run directly: `pnpm --filter @grc/web exec tsx tests/eval/arabicAnalysis.eval.ts`
 * Wired into `pnpm test` via package.json.
 */

import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

// This file lives at apps/web/tests/eval/ — three levels below apps/web.
const appRoot = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
dotenv.config({ path: path.join(appRoot, ".env.local") });
dotenv.config({ path: path.join(appRoot, "..", "..", ".env") });

const SAMPLE_DOCUMENT = `Information Security Policy — Acme Financial Group

1. Access Control: Multi-factor authentication (MFA) is required for all remote access and
all administrative accounts. Access reviews are performed quarterly by IT Security.
2. Logging & Monitoring: Security events are logged centrally and retained for 12 months.
Alerts are configured for anomalous login activity.
3. Third-Party Risk: Vendors with access to company data complete a security questionnaire
prior to onboarding. This policy does not currently define a process for periodic vendor
reassessment.
4. Encryption: Data at rest is encrypted using AES-256. Data in transit uses TLS 1.2 or
higher. Key management procedures are not yet formally documented in this policy.
5. Incident Response: An incident response plan is maintained and tested annually via
tabletop exercises. All incidents must be reported within 24 hours of detection.
6. Review: This policy is reviewed annually by the CISO and approved by executive
leadership.`;

async function main(): Promise<void> {
  const hasKey = Boolean(process.env.OPENAI_API_KEY) && process.env.AI_PROVIDER !== "local";
  if (!hasKey) {
    console.log(
      "SKIP arabicAnalysis.eval — no OPENAI_API_KEY configured (set AI_PROVIDER=openai and " +
        "OPENAI_API_KEY to run this check against a live model).",
    );
    return;
  }

  const { buildAssessmentPrompt, assessmentSchema, narrativeFieldsOf } = await import(
    "../../lib/analysis/prompts/assess_grc_document.v3"
  );
  const { getChatProvider } = await import("../../lib/ai");
  const { missingArabic, containsArabic } = await import("../../lib/i18n/text");

  const chat = getChatProvider();
  const messages = buildAssessmentPrompt({
    fileName: "isms-policy-v1.pdf",
    text: SAMPLE_DOCUMENT,
    categoryLabel: "Cybersecurity",
    locale: "ar",
  });

  console.log(`Requesting an Arabic assessment from ${chat.id} ...`);
  const raw = await chat.complete(messages, { json: true, maxTokens: 20000 });

  const parsed = JSON.parse(raw); // fails loudly (uncaught) if the model didn't return JSON
  const result = assessmentSchema.safeParse(parsed);
  assert(result.success, "response did not match the assessment schema");
  if (!result.success) return; // unreachable — narrows for TypeScript

  const assessment = result.data;
  const narrative = narrativeFieldsOf(assessment);
  const populated = narrative.filter((t): t is string => Boolean(t && t.trim()));
  assert(populated.length > 0, "the model returned no narrative content to check");
  assert(
    !missingArabic(narrative),
    "narrative fields contain no Arabic script — the model returned English content for an " +
      "Arabic-locale request",
  );

  // Every populated narrative field should itself be predominantly Arabic, not just contain
  // one stray Arabic word inside an otherwise-English paragraph.
  const nonArabicFields = populated.filter((t) => !containsArabic(t));
  assert(
    nonArabicFields.length === 0,
    `${nonArabicFields.length}/${populated.length} narrative field(s) contain no Arabic at all: ` +
      nonArabicFields.slice(0, 3).map((t) => JSON.stringify(t.slice(0, 60))).join(", "),
  );

  // Framework names must stay in their canonical English form even in an Arabic response.
  const frameworkNames = assessment.frameworks.map((f) => f.framework).join(" ");
  if (frameworkNames) {
    assert(
      /[A-Za-z]/.test(frameworkNames),
      `framework names were translated out of English: ${frameworkNames}`,
    );
  }

  console.log("PASS arabicAnalysis.eval — Arabic narrative content confirmed:");
  console.log(`  executiveSummary: ${assessment.executiveSummary.slice(0, 120)}...`);
  console.log(`  frameworks: ${frameworkNames || "(none)"}`);
}

function assert(condition: boolean, message: string): asserts condition {
  if (!condition) {
    console.error(`FAIL arabicAnalysis.eval — ${message}`);
    process.exitCode = 1;
    throw new Error(message);
  }
}

main().catch((error) => {
  console.error("FAIL arabicAnalysis.eval —", error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
