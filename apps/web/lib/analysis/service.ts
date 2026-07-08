/**
 * Analysis pipeline service — orchestrates extract → chunk → embed → index → assess → score,
 * with explicit status transitions and fail-safe error handling. `startAnalysis` returns
 * immediately after inserting a new version row and runs the pipeline in the background (the
 * seam for a durable queue/worker in production); the UI polls for status. Registered with
 * `waitUntil` (not a bare un-awaited call) so Vercel's serverless runtime keeps the function
 * instance alive until the pipeline settles — otherwise the platform can freeze/terminate the
 * instance the moment the request's response is sent, silently abandoning the pipeline
 * mid-flight. V2-P2.5: every run creates a new version instead of overwriting the previous one.
 * Node-only.
 */

import { randomUUID } from "node:crypto";
import { waitUntil } from "@vercel/functions";
import { ForbiddenError, NotFoundError } from "@/lib/errors";
import { can } from "@/lib/auth/permissions";
import type { ActorContext } from "@/lib/auth/actor";
import { getChatProvider, getEmbeddingProvider } from "@/lib/ai";
import { blobStore } from "@/lib/storage/blob-store";
import { documentRepository } from "@/lib/documents/repository";
import { DOCUMENT_CATEGORY_LABELS } from "@/lib/documents/types";
import { getRequestLocale } from "@/lib/i18n/request-locale";
import { missingArabic } from "@/lib/i18n/text";
import { logger } from "@/lib/observability/logger";
import type { AppLocale } from "@/i18n/routing";
import { chunkText } from "./chunk";
import { extractText } from "./extract";
import {
  assessmentSchema,
  buildAssessmentPrompt,
  narrativeFieldsOf,
  PROMPT_VERSION,
  type Assessment,
} from "./prompts/assess_grc_document.v3";
import { analysisRepository, type AnalysisWithVersionCount } from "./repository";
import { assertDailyAnalysisAllowance, getDailyAnalysisUsage } from "./usage";
import { computeComplianceScore, computeRiskScore, deriveMaturityLevel } from "./scoring";
import { vectorStore } from "./vector-store";
import type { AnalysisRecord, AnalysisUsage } from "./types";

function assertRead(actor: ActorContext): void {
  if (!can(actor.roles, "read", "knowledge_source")) {
    throw new ForbiddenError("You are not permitted to view analyses.");
  }
}

export async function listAnalyses(actor: ActorContext): Promise<AnalysisWithVersionCount[]> {
  assertRead(actor);
  return analysisRepository.listLatestPerDocument(actor.tenantId);
}

/** The current user's remaining beta analysis budget for today (read-only). */
export async function getAnalysisUsage(actor: ActorContext): Promise<AnalysisUsage> {
  return getDailyAnalysisUsage(actor.userId);
}

export async function listAnalysisVersions(
  actor: ActorContext,
  documentId: string,
): Promise<AnalysisRecord[]> {
  assertRead(actor);
  return analysisRepository.listVersions(actor.tenantId, documentId);
}

/** Fetch one specific version by its own analysis id. */
export async function getAnalysis(
  actor: ActorContext,
  analysisId: string,
): Promise<AnalysisRecord | null> {
  assertRead(actor);
  return analysisRepository.get(actor.tenantId, analysisId);
}

/** Fetch the latest version for a document — the default "analysis for this document" view. */
export async function getLatestAnalysis(
  actor: ActorContext,
  documentId: string,
): Promise<AnalysisRecord | null> {
  assertRead(actor);
  return analysisRepository.getLatest(actor.tenantId, documentId);
}

export async function renameAnalysis(
  actor: ActorContext,
  analysisId: string,
  title: string,
): Promise<AnalysisRecord> {
  if (!can(actor.roles, "update", "knowledge_source")) {
    throw new ForbiddenError("You are not permitted to rename analyses.");
  }
  const trimmed = title.trim().slice(0, 200);
  if (!trimmed) throw new ForbiddenError("Title cannot be empty.");
  const updated = await analysisRepository.patch(actor.tenantId, analysisId, { title: trimmed });
  if (!updated) throw new NotFoundError("Analysis not found.");
  return updated;
}

export async function deleteAnalysis(actor: ActorContext, analysisId: string): Promise<void> {
  if (!can(actor.roles, "delete", "knowledge_source")) {
    throw new ForbiddenError("You are not permitted to delete analyses.");
  }
  await analysisRepository.delete(actor.tenantId, analysisId);
}

export async function startAnalysis(
  actor: ActorContext,
  documentId: string,
): Promise<AnalysisRecord> {
  if (!can(actor.roles, "execute", "knowledge_source")) {
    throw new ForbiddenError("You are not permitted to run analysis.");
  }
  // Beta usage gate: enforced here — the single chokepoint every caller of the analysis
  // pipeline (API, UI, workflow, jobs, tests) passes through — so the daily per-user limit
  // holds regardless of how the run was triggered. Checked before any document lookup or
  // write so a rate-limited request does nothing consequential.
  await assertDailyAnalysisAllowance(actor.userId);
  const doc = await documentRepository.get(actor.tenantId, documentId);
  if (!doc) throw new NotFoundError("Document not found.");

  const version = await analysisRepository.nextVersion(actor.tenantId, documentId);
  const locale = await getRequestLocale();
  const now = new Date().toISOString();
  const record: AnalysisRecord = {
    id: randomUUID(),
    documentId,
    tenantId: actor.tenantId,
    fileName: doc.fileName,
    title: `${doc.fileName} · v${version}`,
    version,
    status: "processing",
    locale,
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
    requestedByUserId: actor.userId,
    requestedByName: actor.userName,
    createdAt: now,
    updatedAt: now,
  };
  await analysisRepository.insert(record);
  await documentRepository.updateStatus(actor.tenantId, documentId, "processing");

  // Background processing — do not block the request, but keep the serverless instance
  // alive via waitUntil until it settles. Errors are captured as a failed status.
  waitUntil(
    runPipeline(
      actor,
      doc.id,
      record.id,
      doc.storageKey,
      doc.kind,
      doc.fileName,
      doc.category,
      locale,
      Date.now(),
    ).catch((error) => markFailed(actor.tenantId, record.id, documentId, error)),
  );

  return record;
}

async function runPipeline(
  actor: ActorContext,
  documentId: string,
  analysisId: string,
  storageKey: string,
  kind: string,
  fileName: string,
  category: string,
  locale: AppLocale,
  startedMs: number,
): Promise<void> {
  // 1. Extract
  const bytes = await blobStore.get(storageKey);
  const { text, pageCount } = await extractText(kind, Buffer.from(bytes));
  if (!text || text.length < 20) {
    throw new Error("No extractable text was found in this document.");
  }

  // 2. Chunk
  const chunks = chunkText(text);

  // 3. Embed + 4. Index
  const embedder = getEmbeddingProvider();
  const embeddings = await embedder.embed(chunks.map((c) => c.text));
  const storedChunks = chunks.map((chunk, i) => ({ ...chunk, embedding: embeddings[i] ?? [] }));
  await vectorStore.put({
    documentId,
    tenantId: actor.tenantId,
    fileName,
    embeddingProvider: embedder.id,
    chunks: storedChunks,
  });

  // 5. Assess (LLM — identifies and classifies only, never scores)
  const chat = getChatProvider();
  const categoryLabel =
    DOCUMENT_CATEGORY_LABELS[category as keyof typeof DOCUMENT_CATEGORY_LABELS] ?? category;
  const assessment = await assess(chat, fileName, text, categoryLabel, locale);

  // 6. Score (deterministic — computed from the assessment above, never LLM-generated)
  const complianceScore = computeComplianceScore(assessment.frameworks);
  const riskScore = computeRiskScore(assessment.findings);
  const maturityLevel = deriveMaturityLevel(complianceScore);

  await analysisRepository.patch(actor.tenantId, analysisId, {
    status: "processed",
    charCount: text.length,
    pageCount,
    chunkCount: chunks.length,
    embeddingProvider: embedder.id,
    chatProvider: chat.id,
    executiveSummary: assessment.executiveSummary,
    complianceOverview: assessment.complianceOverview,
    findings: assessment.findings,
    criticalRisks: assessment.criticalRisks,
    frameworks: assessment.frameworks,
    gaps: assessment.gaps,
    keyTerms: assessment.keyTerms,
    strengths: assessment.strengths,
    weaknesses: assessment.weaknesses,
    recommendations: assessment.recommendations,
    businessImpact: assessment.businessImpact,
    overallPriority: assessment.overallPriority,
    references: assessment.references,
    nextActions: assessment.nextActions,
    complianceScore,
    riskScore,
    maturityLevel,
    completedAt: new Date().toISOString(),
    durationMs: Date.now() - startedMs,
  });
  await documentRepository.updateStatus(actor.tenantId, documentId, "processed");
}

async function markFailed(
  tenantId: string,
  analysisId: string,
  documentId: string,
  error: unknown,
): Promise<void> {
  const message = error instanceof Error ? error.message : "Analysis failed.";
  await analysisRepository.patch(tenantId, analysisId, { status: "failed", error: message });
  await documentRepository.updateStatus(tenantId, documentId, "failed", message);
}

type AttemptResult =
  | { ok: true; data: Assessment }
  | { ok: false; reason: "parse"; raw: string }
  | { ok: false; reason: "schema" };

async function assess(
  chat: ReturnType<typeof getChatProvider>,
  fileName: string,
  text: string,
  categoryLabel: string,
  locale: AppLocale,
): Promise<Assessment> {
  const fallbackSummary =
    locale === "ar" ? "تعذّر إنتاج ملخص لهذا التحليل." : "No summary produced.";
  const unexpectedFormat =
    locale === "ar" ? "أنتج التحليل تنسيقًا غير متوقع." : "Analysis produced an unexpected format.";
  const empty: Assessment = {
    executiveSummary: "",
    complianceOverview: "",
    keyTerms: [],
    findings: [],
    criticalRisks: [],
    frameworks: [],
    gaps: [],
    strengths: [],
    weaknesses: [],
    recommendations: [],
    businessImpact: "",
    overallPriority: { level: "medium", rationale: "" },
    references: [],
    nextActions: [],
  };

  async function attempt(retry: boolean): Promise<AttemptResult> {
    const messages = buildAssessmentPrompt({ fileName, text, categoryLabel, locale, retry });
    // Reasoning models spend completion budget on hidden reasoning before emitting JSON —
    // give ample room so the structured result is not truncated to empty. The v3 schema is
    // larger (consulting-report sections) and Arabic output tokenizes less densely, so this
    // budget is higher than v2's.
    const raw = await chat.complete(messages, { json: true, maxTokens: 20000 });
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return { ok: false, reason: "parse", raw };
    }
    const result = assessmentSchema.safeParse(parsed);
    return result.success ? { ok: true, data: result.data } : { ok: false, reason: "schema" };
  }

  const first = await attempt(false);
  if (first.ok && locale === "ar" && missingArabic(narrativeFieldsOf(first.data))) {
    // The model produced valid JSON but drifted to English despite the language directive —
    // a known reliability gap with `response_format: json_object` (see prompt file). Never
    // translate the existing result: regenerate from the source document so every field is
    // grounded and in Arabic together, not a patched-up mix.
    logger.warn("assessment_language_drift_retry", { fileName, promptVersion: PROMPT_VERSION });
    const retried = await attempt(true);
    if (retried.ok) {
      if (missingArabic(narrativeFieldsOf(retried.data))) {
        logger.error("assessment_language_drift_unresolved", undefined, {
          fileName,
          promptVersion: PROMPT_VERSION,
        });
      }
      return retried.data;
    }
    // Retry failed outright (non-JSON/bad schema) — fall through to the first attempt's
    // (English-drifted) result rather than losing the analysis entirely.
    return first.data;
  }
  if (first.ok) return first.data;

  if (first.reason === "parse") {
    // The model returned non-JSON — degrade to a summary-only result rather than failing.
    return { ...empty, executiveSummary: first.raw.slice(0, 600) || fallbackSummary };
  }
  return { ...empty, executiveSummary: unexpectedFormat };
}

/** Exposed for observability/tests — confirms which prompt version produced a given result. */
export { PROMPT_VERSION };
