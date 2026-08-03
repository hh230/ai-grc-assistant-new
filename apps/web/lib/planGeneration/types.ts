/**
 * The Mission bridge domain types (ADR 0066 §3, §4) — the shapes `lib/planGeneration/service.ts`
 * returns after creating, running, and reading the `generate_governance_plan` Mission, ahead of
 * the human-approval gate. This is the Report stage's data: read-only, nothing persisted yet.
 */

import type {
  EffortSize,
  InferredFramework,
  MaturityRating,
  Priority,
  TimeframeBucket,
} from "@/lib/planExecution/types";

export interface GovernanceReportTopRisk {
  gapId: string;
  severity: string;
  description: string;
  impact: string;
}

export interface GovernanceReportItem {
  id: string;
  pillar: string;
  title: string;
  objective: string;
  expectedOutcome: string;
  rationale: string;
  riskIfSkipped: string;
  timeframeBucket: TimeframeBucket;
  priority: Priority;
  effortSize: EffortSize;
  confidence: number | null;
  dueAt: number | null;
}

export interface GovernanceReportDraft {
  sourceSessionId: string;
  inferredFrameworks: InferredFramework[];
  maturityBaseline: Record<string, MaturityRating>;
  maturityVision: Record<string, MaturityRating>;
  executiveSummary: string;
  topRisks: GovernanceReportTopRisk[];
  items: GovernanceReportItem[];
}

export interface PlanGenerationResult {
  missionId: string;
  /** `null` means the mission never reached the approval gate — a real error (fail-safe:
   * the caller should treat this as failure, never silently proceed to "activate" nothing). */
  decisionId: string | null;
  report: GovernanceReportDraft;
}
