/**
 * Analysis domain types. An analysis is the result of running a document through the AI
 * pipeline (extract → chunk → embed → index → assess → score). V2-P2.5: every run creates a
 * new version instead of overwriting — full history is kept per document.
 */

export const ANALYSIS_STATUSES = ["queued", "processing", "processed", "failed"] as const;
export type AnalysisStatus = (typeof ANALYSIS_STATUSES)[number];

/** Stable API error code returned when a user exceeds the beta daily analysis limit. The UI
 * keys off it to render the localized "try again tomorrow" message. Client-safe (no server
 * imports), so both the browser and the server-only usage module can reference it. */
export const BETA_DAILY_LIMIT_CODE = "beta_daily_limit";

/** Beta usage budget for the current user: how many document analyses they may still start
 * today. Surfaced to the UI (remaining counter + button gating) and enforced server-side. */
export interface AnalysisUsage {
  /** Daily allowance (the beta limit). */
  limit: number;
  /** Analyses this user has already started today. */
  used: number;
  /** Analyses still allowed today — always `max(0, limit - used)`. */
  remaining: number;
  /** ISO timestamp when the counter resets (the start of the next day). */
  resetsAt: string;
}

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

/** A finding serious enough to threaten the business, an audit outcome, or the license to
 *  operate — a curated subset of `findings`, each framed in terms of its business impact. */
export interface CriticalRisk {
  title: string;
  detail: string;
  severity: Severity;
  businessImpact: string;
  framework?: string;
}

export interface FrameworkCoverage {
  framework: string;
  assessment: string;
  alignment: Alignment;
}

/** A specific control/requirement area where the document falls short of a framework. */
export interface Gap {
  area: string;
  description: string;
  severity: Severity;
  framework?: string;
}

/** AI-classified priority (like `severity`); the score fields on `AnalysisRecord` are
 *  computed deterministically by the scoring engine, never asked of the model. */
export interface Recommendation {
  change: string;
  reason: string;
  priority: Priority;
  /** The measurable outcome expected from making this change. */
  expectedImpact: string;
  /** One of the known framework names, if this recommendation maps to one. */
  relatedFramework?: string;
  /** Framework control id or a grounded citation into the source document. */
  reference?: string;
}

export interface OverallPriority {
  level: Priority;
  rationale: string;
}

export interface NextAction {
  action: string;
  priority: Priority;
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

  // AI-grounded results — consulting-report structure (V2 Production Polish)
  /** UI language the report was generated in ("ar" | "en"), for audit/reproducibility. */
  locale?: string;
  executiveSummary?: string;
  complianceOverview?: string;
  findings: AnalysisFinding[];
  criticalRisks: CriticalRisk[];
  frameworks: FrameworkCoverage[];
  gaps: Gap[];
  keyTerms: string[];
  strengths: string[];
  weaknesses: string[];
  recommendations: Recommendation[];
  businessImpact?: string;
  overallPriority?: OverallPriority;
  references: string[];
  nextActions: NextAction[];

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
