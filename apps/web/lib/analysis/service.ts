/**
 * Analysis pipeline service — orchestrates extract → chunk → embed → index → assess → score,
 * with explicit status transitions and fail-safe error handling. `startAnalysis` returns
 * immediately after inserting a new version row and runs the pipeline in the background (the
 * seam for a durable queue/worker in production); the UI polls for status. V2-P2.5: every run
 * creates a new version instead of overwriting the previous one.
 * Node-only.
 */

import { randomUUID } from "node:crypto";
import { ForbiddenError, NotFoundError } from "@/lib/errors";
import { can } from "@/lib/auth/permissions";
import type { ActorContext } from "@/lib/auth/actor";
import { getChatProvider, getEmbeddingProvider } from "@/lib/ai";
import { blobStore } from "@/lib/storage/blob-store";
import { documentRepository } from "@/lib/documents/repository";
import { DOCUMENT_CATEGORY_LABELS } from "@/lib/documents/types";
import { chunkText } from "./chunk";
import { extractText } from "./extract";
import { assessmentSchema, buildAssessmentPrompt, PROMPT_VERSION, type Assessment } from "./prompts/assess_grc_document.v2";
import { analysisRepository, type AnalysisWithVersionCount } from "./repository";
import { computeComplianceScore, computeRiskScore, deriveMaturityLevel } from "./scoring";
import { vectorStore } from "./vector-store";
import type { AnalysisRecord } from "./types";

function assertRead(actor: ActorContext): void {
  if (!can(actor.roles, "read", "knowledge_source")) {
    throw new ForbiddenError("You are not permitted to view analyses.");
  }
}

export async function listAnalyses(actor: ActorContext): Promise<AnalysisWithVersionCount[]> {
  assertRead(actor);
  return analysisRepository.listLatestPerDocument(actor.tenantId);
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
  const doc = await documentRepository.get(actor.tenantId, documentId);
  if (!doc) throw new NotFoundError("Document not found.");

  const version = await analysisRepository.nextVersion(actor.tenantId, documentId);
  const now = new Date().toISOString();
  const record: AnalysisRecord = {
    id: randomUUID(),
    documentId,
    tenantId: actor.tenantId,
    fileName: doc.fileName,
    title: `${doc.fileName} · v${version}`,
    version,
    status: "processing",
    charCount: 0,
    chunkCount: 0,
    findings: [],
    frameworks: [],
    keyTerms: [],
    strengths: [],
    weaknesses: [],
    recommendations: [],
    requestedByUserId: actor.userId,
    requestedByName: actor.userName,
    createdAt: now,
    updatedAt: now,
  };
  await analysisRepository.insert(record);
  await documentRepository.updateStatus(actor.tenantId, documentId, "processing");

  // Background processing — do not block the request. Errors are captured as a failed status.
  void runPipeline(actor, doc.id, record.id, doc.storageKey, doc.kind, doc.fileName, doc.category, Date.now()).catch(
    (error) => markFailed(actor.tenantId, record.id, documentId, error),
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
  const assessment = await assess(chat, fileName, text, categoryLabel);

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
    summary: assessment.summary,
    findings: assessment.findings,
    frameworks: assessment.frameworks,
    keyTerms: assessment.keyTerms,
    strengths: assessment.strengths,
    weaknesses: assessment.weaknesses,
    recommendations: assessment.recommendations,
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

async function assess(
  chat: ReturnType<typeof getChatProvider>,
  fileName: string,
  text: string,
  categoryLabel: string,
): Promise<Assessment> {
  const messages = buildAssessmentPrompt({ fileName, text, categoryLabel });

  // Reasoning models spend completion budget on hidden reasoning before emitting JSON —
  // give ample room so the structured result is not truncated to empty.
  const raw = await chat.complete(messages, { json: true, maxTokens: 16000 });
  const empty: Assessment = {
    summary: "",
    keyTerms: [],
    findings: [],
    frameworks: [],
    strengths: [],
    weaknesses: [],
    recommendations: [],
  };
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // The model returned non-JSON — degrade to a summary-only result rather than failing.
    return { ...empty, summary: raw.slice(0, 600) || "No summary produced." };
  }
  const result = assessmentSchema.safeParse(parsed);
  if (!result.success) {
    return { ...empty, summary: "Analysis produced an unexpected format." };
  }
  return result.data;
}

/** Exposed for observability/tests — confirms which prompt version produced a given result. */
export { PROMPT_VERSION };
