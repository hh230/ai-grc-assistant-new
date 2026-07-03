/**
 * Versioned prompt artifact (CLAUDE.md §22 — "prompts live in versioned, reviewable files,
 * never hardcoded inline"). v3 (V2 Production Polish) restructures the grounded output into
 * a full consulting-report shape (Executive Summary, Compliance Overview, Key Findings,
 * Critical Risks, Gap Analysis, Recommended Changes, Business Impact, Priority, References,
 * Next Actions) and makes the prompt locale-aware: when the tenant's UI language is Arabic,
 * every narrative field is generated in professional Modern Standard Arabic, matching the
 * tone of a Big-4 GRC advisory deliverable, while framework names/codes stay in their
 * internationally recognized English form. The model only *identifies and classifies*
 * (severity, alignment, priority) — it never produces a numeric score; `lib/analysis/scoring`
 * computes every score deterministically from this structured output.
 *
 * Language adherence hardening: `response_format: json_object` measurably increases the odds
 * a model drifts back to English for individual string fields despite an explicit language
 * instruction (the schema shape itself is described in English, and JSON-mode decoding pulls
 * toward the training distribution of JSON, which skews English). To counter this the Arabic
 * directive is stated at the very start of the system prompt (primacy), restated inline next
 * to every field in the schema description, and restated once more at the end of the user
 * message (recency) — and `lib/analysis/service.ts` verifies the response actually contains
 * Arabic script and regenerates once with `buildAssessmentPrompt({ ..., retry: true })` if not.
 */

import { z } from "zod";
import type { ChatMessage } from "@/lib/ai";
import type { AppLocale } from "@/i18n/routing";
import { FRAMEWORKS } from "@/lib/frameworks/catalog";

export const PROMPT_VERSION = "assess_grc_document.v3";

const MAX_PROMPT_CHARS = 14_000;

const severity = z.enum(["high", "medium", "low", "info"]).catch("info");
const priority = z.enum(["high", "medium", "low"]).catch("medium");

export const assessmentSchema = z.object({
  executiveSummary: z.string().default(""),
  complianceOverview: z.string().default(""),
  keyTerms: z.array(z.string()).default([]),
  findings: z
    .array(
      z.object({
        title: z.string(),
        detail: z.string(),
        severity,
        framework: z.string().optional(),
      }),
    )
    .default([]),
  criticalRisks: z
    .array(
      z.object({
        title: z.string(),
        detail: z.string(),
        severity,
        businessImpact: z.string(),
        framework: z.string().optional(),
      }),
    )
    .default([]),
  frameworks: z
    .array(
      z.object({
        framework: z.string(),
        assessment: z.string(),
        alignment: z.enum(["strong", "partial", "gap", "unknown"]).catch("unknown"),
      }),
    )
    .default([]),
  gaps: z
    .array(
      z.object({
        area: z.string(),
        description: z.string(),
        severity,
        framework: z.string().optional(),
      }),
    )
    .default([]),
  strengths: z.array(z.string()).default([]),
  weaknesses: z.array(z.string()).default([]),
  recommendations: z
    .array(
      z.object({
        change: z.string(),
        reason: z.string(),
        priority,
        expectedImpact: z.string(),
        relatedFramework: z.string().optional(),
        reference: z.string().optional(),
      }),
    )
    .default([]),
  businessImpact: z.string().default(""),
  overallPriority: z
    .object({ level: priority, rationale: z.string().default("") })
    .default({ level: "medium", rationale: "" }),
  references: z.array(z.string()).default([]),
  nextActions: z
    .array(z.object({ action: z.string(), priority }))
    .default([]),
});

export type Assessment = z.infer<typeof assessmentSchema>;

/** Every narrative (free-text) field a language-adherence check should inspect — excludes
 *  framework names, control references, and enum-like fields, which are expected to stay in
 *  English (or a mix) even for an Arabic-locale response. Shared by the retry guard in
 *  `lib/analysis/service.ts` and the Arabic-generation regression check. */
export function narrativeFieldsOf(a: Assessment): Array<string | undefined> {
  return [
    a.executiveSummary,
    a.complianceOverview,
    a.businessImpact,
    a.overallPriority?.rationale,
    ...a.findings.flatMap((f) => [f.title, f.detail]),
    ...a.criticalRisks.flatMap((r) => [r.title, r.detail, r.businessImpact]),
    ...a.frameworks.map((f) => f.assessment),
    ...a.gaps.flatMap((g) => [g.area, g.description]),
    ...a.strengths,
    ...a.weaknesses,
    ...a.recommendations.flatMap((r) => [r.change, r.reason, r.expectedImpact]),
    ...a.nextActions.map((n) => n.action),
  ];
}

const KNOWN_FRAMEWORK_NAMES = [
  ...FRAMEWORKS.map((f) => f.shortName),
  "SAMA",
  "PDPL",
] as const;

/** Every narrative field's description gets an inline `(language)` reminder — repetition at
 *  the schema level measurably reduces English drift on individual fields in JSON mode. */
function responseShape(locale: AppLocale): string {
  const lang = locale === "ar" ? "بالعربية الفصحى" : "in English";
  return (
    `{"executiveSummary": string ${lang} (3-5 sentences, senior-consultant tone), ` +
    `"complianceOverview": string ${lang} (2-4 sentences synthesizing overall alignment across frameworks), ` +
    `"keyTerms": string[] (5-10 salient terms, framework/control terminology may stay in its original form), ` +
    `"findings": [{"title": string ${lang}, "detail": string ${lang}, "severity": "high"|"medium"|"low"|"info", "framework": string?}], ` +
    `"criticalRisks": [{"title": string ${lang}, "detail": string ${lang}, "severity": "high"|"medium"|"low", "businessImpact": string ${lang}, "framework": string?}] ` +
    `(only the findings serious enough to threaten the business, audit outcome, or license to operate — a subset, not a copy, of findings), ` +
    `"frameworks": [{"framework": string (exact known framework name, English), "assessment": string ${lang} (1 sentence), "alignment": "strong"|"partial"|"gap"|"unknown"}], ` +
    `"gaps": [{"area": string ${lang} (the specific control/requirement area), "description": string ${lang} (what is missing and what is required), "severity": "high"|"medium"|"low"|"info", "framework": string?}], ` +
    `"strengths": string[] ${lang} (what the document already does well, grounded in its text), ` +
    `"weaknesses": string[] ${lang} (gaps or omissions, grounded in its text), ` +
    `"recommendations": [{"change": string ${lang} (the specific suggested change), "reason": string ${lang} (why it matters), ` +
    `"priority": "high"|"medium"|"low", "expectedImpact": string ${lang} (the measurable outcome of making this change), ` +
    `"relatedFramework": string? (one of the known framework names, English, if applicable), ` +
    `"reference": string? (a framework control id, or a citation into the document e.g. "Section 4")}], ` +
    `"businessImpact": string ${lang} (2-4 sentences on the business consequence of the current state — audit, regulatory, operational, reputational), ` +
    `"overallPriority": {"level": "high"|"medium"|"low", "rationale": string ${lang} (1-2 sentences)}, ` +
    `"references": string[] (framework control ids and document sections cited above, deduplicated), ` +
    `"nextActions": [{"action": string ${lang} (a concrete, assignable next step), "priority": "high"|"medium"|"low"}]}`
  );
}

function languageInstruction(locale: AppLocale): string {
  if (locale === "ar") {
    return (
      "RESPOND ONLY IN ARABIC. Every narrative string in the JSON you produce — " +
      "executiveSummary, complianceOverview, every findings[].title/detail, every " +
      "criticalRisks[].title/detail/businessImpact, every frameworks[].assessment, every " +
      "gaps[].area/description, strengths, weaknesses, every recommendations[].change/" +
      "reason/expectedImpact, businessImpact, overallPriority.rationale, and every " +
      "nextActions[].action — MUST be written in professional, formal Modern Standard " +
      "Arabic (فصحى), in the register of a Big-4 (Deloitte/PwC/KPMG) advisory deliverable. " +
      "This is a hard requirement, not a stylistic preference: a response containing English " +
      "sentences in any of those fields is a failed response. The ONLY text that stays in " +
      "English is the exact, internationally recognized framework name/code when one of " +
      `these is referenced (${KNOWN_FRAMEWORK_NAMES.join(", ")}) and standard technical ` +
      "acronyms (e.g. MFA, TLS, AES-256). Do not transliterate Arabic into Latin letters, " +
      "and do not switch to English mid-response."
    );
  }
  return (
    "Write every narrative field in professional, formal business English, in the register of " +
    "a Big-4 (Deloitte/PwC/KPMG) advisory deliverable."
  );
}

export function buildAssessmentPrompt(input: {
  fileName: string;
  text: string;
  categoryLabel: string;
  locale: AppLocale;
  /** Set on a regeneration attempt after the first response failed the Arabic-content check
   *  (`lib/analysis/service.ts`) — escalates the language directive rather than repeating it
   *  verbatim, since models are more likely to correct course on a differently-worded retry. */
  retry?: boolean;
}): ChatMessage[] {
  const langDirective = languageInstruction(input.locale);
  const retryPrefix =
    input.retry && input.locale === "ar"
      ? "CORRECTION REQUIRED: your previous response to an equivalent request was written in " +
        "English. That was wrong. This time, every narrative field must be Arabic from the " +
        "first word. "
      : "";

  return [
    {
      role: "system",
      content:
        // Language directive first (primacy) — the single highest-priority instruction.
        `${retryPrefix}${langDirective} ` +
        "You are a senior GRC (Governance, Risk & Compliance) advisory consultant producing a " +
        "client-ready assessment report, not a chat answer. You assess documents against common " +
        `frameworks (${KNOWN_FRAMEWORK_NAMES.join(", ")}). Ground every statement in the provided ` +
        "text — never invent control IDs or facts, and never fabricate a citation. When you name " +
        "a framework, use one of the exact names listed above if it applies. You identify and " +
        "classify only (severity, alignment, priority) — never output a numeric score of any " +
        "kind; scoring is computed separately. Avoid generic AI filler phrasing (e.g. \"it is " +
        "important to note\", \"in today's digital landscape\"); write with the precision and " +
        "authority of a consultant who has actually read the document. Respond ONLY with a JSON " +
        "object matching the requested schema — no markdown, no prose outside the JSON.",
    },
    {
      role: "user",
      content:
        `Document: "${input.fileName}" (classified as: ${input.categoryLabel})\n\n` +
        `Analyze the document below and return JSON with this exact shape:\n${responseShape(input.locale)}\n\n` +
        `--- DOCUMENT START ---\n${input.text.slice(0, MAX_PROMPT_CHARS)}\n--- DOCUMENT END ---\n\n` +
        // Language directive again, last (recency), right before the model starts generating.
        (input.locale === "ar"
          ? "Reminder before you respond: write the JSON values in Modern Standard Arabic, " +
            "not English — only framework names/codes and technical acronyms stay in English."
          : ""),
    },
  ];
}
