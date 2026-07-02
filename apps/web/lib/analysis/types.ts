/**
 * Analysis domain types. An analysis is the result of running a document through the AI
 * pipeline (extract → chunk → embed → index → assess → score). V2-P2.5: every run creates a
 * new version instead of overwriting — full history is kept per document.
 */

export const ANALYSIS_STATUSES = ["queued", "processing", "processed", "failed"] as const;
export type AnalysisStatus = (typeof ANALYSIS_STATUSES)[number];

export type Severity = "high" | "medium" | "low" | "info";
export type Alignment = "strong" | "partial" | "gap" | "unknown";
export type Priority = "high" | "medium" | "low";

export interface Chunk {
  index: number;
  text: string;
  charStart: number;
  charEnd: number;
}

export interface StoredChunk extends Chunk {
  embedding: number[];
}

export interface AnalysisFinding {
  title: string;
  detail: string;
  severity: Severity;
  framework?: string;
}

export interface FrameworkCoverage {
  framework: string;
  assessment: string;
  alignment: Alignment;
}

/** AI-classified priority (like `severity`); the score fields on `AnalysisRecord` are
 *  computed deterministically by the scoring engine, never asked of the model. */
export interface Recommendation {
  change: string;
  reason: string;
  priority: Priority;
  /** Framework control id or a grounded citation into the source document. */
  reference?: string;
}

export interface AnalysisRecord {
  /** Unique per version — no longer equal to the document id. */
  id: string;
  documentId: string;
  tenantId: string;
  fileName: string;
  /** User-editable label (rename). Defaults to `"${fileName} · v${version}"`. */
  title: string;
  /** 1, 2, 3, … — incremented on every re-run for the same document. */
  version: number;
  status: AnalysisStatus;
  error?: string;

  // pipeline metrics
  charCount: number;
  pageCount?: number;
  chunkCount: number;
  embeddingProvider?: string;
  chatProvider?: string;

  // AI-grounded results
  summary?: string;
  findings: AnalysisFinding[];
  frameworks: FrameworkCoverage[];
  keyTerms: string[];
  strengths: string[];
  weaknesses: string[];
  recommendations: Recommendation[];

  // deterministically computed by lib/analysis/scoring — never LLM-generated
  complianceScore?: number;
  riskScore?: number;
  maturityLevel?: string;

  // audit
  requestedByUserId: string;
  requestedByName: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  durationMs?: number;
}
