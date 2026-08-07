/**
 * Real, per-tenant dashboard metrics — no static/illustrative numbers. Every figure is
 * computed from the signed-in organization's own analysis history
 * (`analysisRepository`), scoped to the selected date range. This is the single source of
 * truth consumed by the Compliance/Risk score cards, the Executive Summary, and the PDF
 * export, so what's shown on screen always matches what gets exported.
 */

import type { ActorContext } from "@/lib/auth/actor";
import { analysisRepository } from "@/lib/analysis/repository";
import type { AnalysisWithVersionCount } from "@/lib/analysis/repository";
import type { DashboardRangeDays } from "./range";

export { DASHBOARD_RANGE_DAYS, DEFAULT_DASHBOARD_RANGE, parseDashboardRange } from "./range";
export type { DashboardRangeDays } from "./range";

export type ComplianceBand = "veryLow" | "medium" | "high" | "none";
export type RiskBand = "low" | "medium" | "high" | "none";

export interface ScoreTrend {
  delta: number;
  direction: "up" | "down" | "flat";
}

export interface DashboardMetrics {
  rangeDays: DashboardRangeDays;
  /** Analyses (latest version per document) completed within the selected range. */
  analyses: AnalysisWithVersionCount[];
  documentsAnalyzedCount: number;
  complianceScore: number | null;
  riskScore: number | null;
  complianceBand: ComplianceBand;
  riskBand: RiskBand;
  /** vs. the immediately preceding period of equal length — null with too little history. */
  complianceTrend: ScoreTrend | null;
  riskTrend: ScoreTrend | null;
  frameworksUsed: string[];
  topGaps: { area: string; description: string; framework?: string }[];
  topRecommendations: { change: string; reason: string; framework?: string }[];
  latestAnalyzedAt: string | null;
}

function average(values: number[]): number | null {
  if (values.length === 0) return null;
  return Math.round(values.reduce((a, b) => a + b, 0) / values.length);
}

// Aligned with the existing compliance maturity bands (lib/analysis/scoring/index.ts
// `deriveMaturityLevel`): Initial (<30) -> veryLow, Developing/Defined (30-74) -> medium,
// Managed/Optimized (>=75) -> high. Reusing the same cut points keeps the dashboard's
// language consistent with the per-document analysis detail view.
function complianceBandOf(score: number | null): ComplianceBand {
  if (score == null) return "none";
  if (score < 30) return "veryLow";
  if (score < 75) return "medium";
  return "high";
}

function riskBandOf(score: number | null): RiskBand {
  if (score == null) return "none";
  if (score < 30) return "low";
  if (score < 60) return "medium";
  return "high";
}

function trendOf(current: number | null, previous: number | null): ScoreTrend | null {
  if (current == null || previous == null) return null;
  const delta = current - previous;
  return { delta: Math.round(delta * 10) / 10, direction: delta > 0 ? "up" : delta < 0 ? "down" : "flat" };
}

export async function getDashboardMetrics(
  actor: ActorContext,
  rangeDays: DashboardRangeDays,
): Promise<DashboardMetrics> {
  const all = await analysisRepository.listLatestPerDocument(actor.tenantId);
  const dayMs = 24 * 60 * 60 * 1000;
  const cutoff = Date.now() - rangeDays * dayMs;
  const previousCutoff = cutoff - rangeDays * dayMs;
  const analyses = all.filter(
    (a) => a.status === "processed" && new Date(a.createdAt).getTime() >= cutoff,
  );
  const previousAnalyses = all.filter((a) => {
    const t = new Date(a.createdAt).getTime();
    return a.status === "processed" && t >= previousCutoff && t < cutoff;
  });

  const complianceScore = average(
    analyses.map((a) => a.complianceScore).filter((v): v is number => v != null),
  );
  const riskScore = average(analyses.map((a) => a.riskScore).filter((v): v is number => v != null));
  const previousComplianceScore = average(
    previousAnalyses.map((a) => a.complianceScore).filter((v): v is number => v != null),
  );
  const previousRiskScore = average(
    previousAnalyses.map((a) => a.riskScore).filter((v): v is number => v != null),
  );

  const frameworksUsed = [...new Set(analyses.flatMap((a) => a.frameworks.map((f) => f.framework)))];

  const highPriorityRecs = analyses
    .flatMap((a) => a.recommendations.map((r) => ({ ...r, analyzedAt: a.createdAt })))
    .filter((r) => r.priority === "high")
    .sort((a, b) => b.analyzedAt.localeCompare(a.analyzedAt));
  const topRecommendations = highPriorityRecs
    .slice(0, 5)
    .map((r) => ({ change: r.change, reason: r.reason, framework: r.relatedFramework }));

  const severityWeight: Record<string, number> = { high: 0, medium: 1, low: 2, info: 3 };
  const allGaps = analyses
    .flatMap((a) => a.gaps.map((g) => ({ ...g, analyzedAt: a.createdAt })))
    .sort(
      (a, b) =>
        (severityWeight[a.severity] ?? 9) - (severityWeight[b.severity] ?? 9) ||
        b.analyzedAt.localeCompare(a.analyzedAt),
    );
  const topGaps = allGaps
    .slice(0, 5)
    .map((g) => ({ area: g.area, description: g.description, framework: g.framework }));

  const latestAnalyzedAt =
    analyses
      .map((a) => a.completedAt ?? a.createdAt)
      .sort((a, b) => b.localeCompare(a))[0] ?? null;

  return {
    rangeDays,
    analyses,
    documentsAnalyzedCount: analyses.length,
    complianceScore,
    riskScore,
    complianceBand: complianceBandOf(complianceScore),
    riskBand: riskBandOf(riskScore),
    complianceTrend: trendOf(complianceScore, previousComplianceScore),
    riskTrend: trendOf(riskScore, previousRiskScore),
    frameworksUsed,
    topGaps,
    topRecommendations,
    latestAnalyzedAt,
  };
}
