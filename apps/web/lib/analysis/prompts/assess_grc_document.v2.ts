/**
 * Versioned prompt artifact (CLAUDE.md §22 — "prompts live in versioned, reviewable files,
 * never hardcoded inline"). v2 (V2-P2.5) adds `strengths`, `weaknesses`, and `recommendations`
 * to the grounded output, and takes the document's classification as context. The model only
 * *identifies and classifies* (severity, alignment, recommendation priority) — it never
 * produces a numeric score; `lib/analysis/scoring` computes every score deterministically from
 * this structured output.
 */

import { z } from "zod";
import type { ChatMessage } from "@/lib/ai";
import { FRAMEWORKS } from "@/lib/frameworks/catalog";

export const PROMPT_VERSION = "assess_grc_document.v2";

const MAX_PROMPT_CHARS = 14_000;

export const assessmentSchema = z.object({
  summary: z.string(),
  keyTerms: z.array(z.string()).default([]),
  findings: z
    .array(
      z.object({
        title: z.string(),
        detail: z.string(),
        severity: z.enum(["high", "medium", "low", "info"]).catch("info"),
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
  strengths: z.array(z.string()).default([]),
  weaknesses: z.array(z.string()).default([]),
  recommendations: z
    .array(
      z.object({
        change: z.string(),
        reason: z.string(),
        priority: z.enum(["high", "medium", "low"]).catch("medium"),
        reference: z.string().optional(),
      }),
    )
    .default([]),
});

export type Assessment = z.infer<typeof assessmentSchema>;

const KNOWN_FRAMEWORK_NAMES = [
  ...FRAMEWORKS.map((f) => f.shortName),
  "SAMA",
  "PDPL",
] as const;

export function buildAssessmentPrompt(input: {
  fileName: string;
  text: string;
  categoryLabel: string;
}): ChatMessage[] {
  return [
    {
      role: "system",
      content:
        "You are a meticulous GRC (Governance, Risk & Compliance) analyst. You assess documents " +
        `against common frameworks (${KNOWN_FRAMEWORK_NAMES.join(", ")}). Ground every statement ` +
        "in the provided text — never invent control IDs or facts. When you name a framework, use " +
        "one of the exact names listed above if it applies. You identify and classify only " +
        "(severity, alignment, recommendation priority) — never output a numeric score of any " +
        "kind; scoring is computed separately. Respond ONLY with a JSON object matching the " +
        "requested schema.",
    },
    {
      role: "user",
      content:
        `Document: "${input.fileName}" (classified as: ${input.categoryLabel})\n\n` +
        `Analyze the document below and return JSON with this exact shape:\n` +
        `{"summary": string (2-4 sentences), "keyTerms": string[] (5-10 salient terms), ` +
        `"findings": [{"title": string, "detail": string, "severity": "high"|"medium"|"low"|"info", "framework": string?}], ` +
        `"frameworks": [{"framework": string, "assessment": string (1 sentence), "alignment": "strong"|"partial"|"gap"|"unknown"}], ` +
        `"strengths": string[] (what the document already does well, grounded in its text), ` +
        `"weaknesses": string[] (gaps or omissions, grounded in its text), ` +
        `"recommendations": [{"change": string (the specific change to make), "reason": string (why it matters), ` +
        `"priority": "high"|"medium"|"low", "reference": string? (a framework control id if this maps to one, ` +
        `otherwise a citation into the document e.g. "Section 4")}]}.\n\n` +
        `--- DOCUMENT START ---\n${input.text.slice(0, MAX_PROMPT_CHARS)}\n--- DOCUMENT END ---`,
    },
  ];
}
