/**
 * Real-tenant executive insights for the dashboard (V2 Production Polish) — distinct from
 * `needsAttention.ts`, which is built from the static illustrative demo dataset
 * (`lib/data.ts`, kept for the investor-demo narrative). This reads the tenant's actual
 * risks, documents, and analyses and surfaces a signal only when that data exists, so a
 * fresh tenant with no real activity yet renders nothing here. Node-only.
 */

import type { ActorContext } from "@/lib/auth/actor";
import { listRisks } from "@/lib/risk/service";
import { toRiskSummary } from "@/lib/risk/types";
import { documentRepository } from "@/lib/documents/repository";
import { analysisRepository } from "@/lib/analysis/repository";
import type { Tone } from "@/lib/design/tone";

export interface LiveInsight {
  id: string;
  tone: Tone;
  icon: "risk" | "document" | "analysis" | "trend" | "action";
  titleKey: string;
  titleValues: Record<string, string | number>;
  detailKey: string;
  detailValues: Record<string, string | number>;
  href: string;
}

export async function getLiveInsights(actor: ActorContext): Promise<LiveInsight[]> {
  const [risks, documents, analyses] = await Promise.all([
    listRisks(actor).then((rs) => rs.map(toRiskSummary)),
    documentRepository.list(actor.tenantId),
    analysisRepository.listLatestPerDocument(actor.tenantId),
  ]);

  const items: LiveInsight[] = [];

  // Highest-priority open risk.
  const openRisks = risks
    .filter((r) => r.status === "open" || r.status === "mitigating")
    .sort((a, b) => b.inherentScore - a.inherentScore);
  const topRisk = openRisks[0];
  if (topRisk) {
    items.push({
      id: `risk-${topRisk.id}`,
      tone: topRisk.severity === "critical" || topRisk.severity === "high" ? "danger" : "warning",
      icon: "risk",
      titleKey: "topRisk",
      titleValues: { title: topRisk.title },
      detailKey: "topRiskDetail",
      detailValues: { score: topRisk.inherentScore, count: openRisks.length },
      href: "/risk-register",
    });
  }

  // Documents awaiting review (uploaded but never analyzed, or last run failed).
  const awaiting = documents.filter((d) => d.status === "uploaded" || d.status === "failed");
  if (awaiting.length > 0) {
    items.push({
      id: "documents-awaiting",
      tone: "accent",
      icon: "document",
      titleKey: "documentsAwaiting",
      titleValues: { count: awaiting.length },
      detailKey: "documentsAwaitingDetail",
      detailValues: { name: awaiting[0]!.fileName },
      href: "/upload",
    });
  }

  // Most recently analyzed document.
  const processed = analyses
    .filter((a) => a.status === "processed" && a.completedAt)
    .sort((a, b) => (b.completedAt ?? "").localeCompare(a.completedAt ?? ""));
  const latest = processed[0];
  if (latest) {
    items.push({
      id: `analysis-${latest.id}`,
      tone: "success",
      icon: "analysis",
      titleKey: "recentlyAnalyzed",
      titleValues: { name: latest.fileName },
      detailKey: "recentlyAnalyzedDetail",
      detailValues: { score: latest.complianceScore ?? 0 },
      href: `/analysis?doc=${latest.documentId}`,
    });
  }

  // Compliance trend across every scored analysis on record.
  const scored = processed.filter((a) => a.complianceScore != null);
  if (scored.length >= 2) {
    const midpoint = Math.floor(scored.length / 2);
    const recentAvg = average(scored.slice(0, midpoint).map((a) => a.complianceScore!));
    const olderAvg = average(scored.slice(midpoint).map((a) => a.complianceScore!));
    const delta = Math.round(recentAvg - olderAvg);
    if (delta !== 0) {
      items.push({
        id: "compliance-trend",
        tone: delta > 0 ? "success" : "warning",
        icon: "trend",
        titleKey: delta > 0 ? "trendUp" : "trendDown",
        titleValues: { delta: Math.abs(delta) },
        detailKey: "trendDetail",
        detailValues: { count: scored.length },
        href: "/analysis",
      });
    }
  }

  // Findings/recommendations still needing attention across the latest analyses.
  const openRecommendations = processed.reduce(
    (sum, a) => sum + a.recommendations.filter((r) => r.priority === "high").length,
    0,
  );
  if (openRecommendations > 0) {
    items.push({
      id: "high-priority-recommendations",
      tone: "danger",
      icon: "action",
      titleKey: "highPriorityRecommendations",
      titleValues: { count: openRecommendations },
      detailKey: "highPriorityRecommendationsDetail",
      detailValues: {},
      href: "/analysis",
    });
  }

  const rank: Record<Tone, number> = { danger: 0, warning: 1, accent: 2, success: 3, neutral: 4 };
  return items.sort((a, b) => rank[a.tone] - rank[b.tone]);
}

function average(values: number[]): number {
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}
