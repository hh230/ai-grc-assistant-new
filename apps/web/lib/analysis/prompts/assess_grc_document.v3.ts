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

const KNOWN_FRAMEWORK_NAMES = [
  ...FRAMEWORKS.map((f) => f.shortName),
  "SAMA",
  "PDPL",
] as const;

const RESPONSE_SHAPE =
  `{"executiveSummary": string (3-5 sentences, senior-consultant tone), ` +
  `"complianceOverview": string (2-4 sentences synthesizing overall alignment across frameworks), ` +
  `"keyTerms": string[] (5-10 salient terms), ` +
  `"findings": [{"title": string, "detail": string, "severity": "high"|"medium"|"low"|"info", "framework": string?}], ` +
  `"criticalRisks": [{"title": string, "detail": string, "severity": "high"|"medium"|"low", "businessImpact": string, "framework": string?}] ` +
  `(only the findings serious enough to threaten the business, audit outcome, or license to operate — a subset, not a copy, of findings), ` +
  `"frameworks": [{"framework": string, "assessment": string (1 sentence), "alignment": "strong"|"partial"|"gap"|"unknown"}], ` +
  `"gaps": [{"area": string (the specific control/requirement area), "description": string (what is missing and what is required), "severity": "high"|"medium"|"low"|"info", "framework": string?}], ` +
  `"strengths": string[] (what the document already does well, grounded in its text), ` +
  `"weaknesses": string[] (gaps or omissions, grounded in its text), ` +
  `"recommendations": [{"change": string (the specific suggested change), "reason": string (why it matters), ` +
  `"priority": "high"|"medium"|"low", "expectedImpact": string (the measurable outcome of making this change), ` +
  `"relatedFramework": string? (one of the known framework names, if applicable), ` +
  `"reference": string? (a framework control id, or a citation into the document e.g. "Section 4")}], ` +
  `"businessImpact": string (2-4 sentences on the business consequence of the current state — audit, regulatory, operational, reputational), ` +
  `"overallPriority": {"level": "high"|"medium"|"low", "rationale": string (1-2 sentences)}, ` +
  `"references": string[] (framework control ids and document sections cited above, deduplicated), ` +
  `"nextActions": [{"action": string (a concrete, assignable next step), "priority": "high"|"medium"|"low"}]}`;

function languageInstruction(locale: AppLocale): string {
  if (locale === "ar") {
    return (
      "Write EVERY narrative field — executiveSummary, complianceOverview, findings, " +
      "criticalRisks, gaps, strengths, weaknesses, recommendations, businessImpact, " +
      "overallPriority.rationale, references, and nextActions — in professional, formal " +
      "Modern Standard Arabic (فصحى), in the register of a Big-4 (Deloitte/PwC/KPMG) advisory " +
      "deliverable. Do not mix in English words or transliterate, except for the exact " +
      `internationally recognized framework names/codes (${KNOWN_FRAMEWORK_NAMES.join(", ")}) ` +
      "and standard technical acronyms, which must stay in English exactly as listed. Never " +
      "respond in English."
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
}): ChatMessage[] {
  return [
    {
      role: "system",
      content:
        "You are a senior GRC (Governance, Risk & Compliance) advisory consultant producing a " +
        "client-ready assessment report, not a chat answer. You assess documents against common " +
        `frameworks (${KNOWN_FRAMEWORK_NAMES.join(", ")}). Ground every statement in the provided ` +
        "text — never invent control IDs or facts, and never fabricate a citation. When you name " +
        "a framework, use one of the exact names listed above if it applies. You identify and " +
        "classify only (severity, alignment, priority) — never output a numeric score of any " +
        "kind; scoring is computed separately. Avoid generic AI filler phrasing (e.g. \"it is " +
        "important to note\", \"in today's digital landscape\"); write with the precision and " +
        "authority of a consultant who has actually read the document. " +
        languageInstruction(input.locale) +
        " Respond ONLY with a JSON object matching the requested schema — no markdown, no prose " +
        "outside the JSON.",
    },
    {
      role: "user",
      content:
        `Document: "${input.fileName}" (classified as: ${input.categoryLabel})\n\n` +
        `Analyze the document below and return JSON with this exact shape:\n${RESPONSE_SHAPE}\n\n` +
        `--- DOCUMENT START ---\n${input.text.slice(0, MAX_PROMPT_CHARS)}\n--- DOCUMENT END ---`,
    },
  ];
}
