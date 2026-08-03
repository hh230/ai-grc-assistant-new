import { Library, TriangleAlert, ClipboardList, type LucideIcon } from "lucide-react";
import { getLocale } from "next-intl/server";
import type { ActorContext } from "@/lib/auth/actor";
import { analysisRepository } from "@/lib/analysis/repository";
import { computeCoverage } from "@/lib/governance/coverage";
import { FRAMEWORKS } from "@/lib/frameworks/catalog";
import { listRisks } from "@/lib/risk/service";
import { scoreOf, severityOf } from "@/lib/risk/types";
import type { Tone } from "@/lib/design/tone";
import type { AppLocale } from "@/i18n/routing";
import { formatRelativeTime } from "@/lib/dashboard/relativeTime";

export interface NeedsAttentionItem {
  id: string;
  icon: LucideIcon;
  tone: Tone;
  titleKey: string;
  titleValues: Record<string, string | number>;
  /** Resolved via the `riskRegister.severity` namespace before use as `{severity}` — never
   * interpolate the raw English enum directly into a localized sentence. */
  severityKey?: "low" | "medium" | "high" | "critical";
  detailKey: string;
  detailValues: Record<string, string | number>;
  href: string;
}

const FRAMEWORK_GAP_THRESHOLD = 80;

/**
 * Band 2 of the dashboard (V2-P3 design proposal §11) — "what needs my attention?". Was
 * built from static illustrative demo arrays (see git history); rewired post-v2.0.1 audit to
 * derive strictly from the tenant's own real data: framework coverage (`computeCoverage`,
 * same source `ActiveFrameworks`/`Controls` use), the real risk register, and in-flight
 * analyses — never a fabricated dataset. Ranked danger-first, then warning.
 */
export async function getNeedsAttentionItems(actor: ActorContext): Promise<NeedsAttentionItem[]> {
  const items: NeedsAttentionItem[] = [];
  const knownFrameworkIds = new Set(FRAMEWORKS.map((f) => f.id));

  const [coverage, risks, analyses, locale] = await Promise.all([
    computeCoverage(actor),
    listRisks(actor),
    analysisRepository.listLatestPerDocument(actor.tenantId),
    getLocale() as Promise<AppLocale>,
  ]);

  for (const framework of coverage.frameworks) {
    if (framework.coveragePct >= FRAMEWORK_GAP_THRESHOLD) continue;
    items.push({
      id: `framework-${framework.id}`,
      icon: Library,
      tone: framework.coveragePct < 40 ? "danger" : "warning",
      titleKey: "frameworkGap",
      titleValues: { code: framework.shortName },
      detailKey: "frameworkGapDetail",
      detailValues: {
        coverage: framework.coveragePct,
        remaining: framework.total - framework.covered,
      },
      href: knownFrameworkIds.has(framework.id) ? `/frameworks/${framework.id}` : "/frameworks",
    });
  }

  for (const risk of risks) {
    if (risk.status !== "open" && risk.status !== "mitigating") continue;
    const severity = severityOf(scoreOf(risk.likelihood, risk.impact));
    if (severity !== "high" && severity !== "critical") continue;
    items.push({
      id: `risk-${risk.id}`,
      icon: TriangleAlert,
      tone: severity === "critical" ? "danger" : "warning",
      titleKey: "riskExposure",
      titleValues: { title: risk.title },
      severityKey: severity,
      detailKey: "riskExposureDetail",
      detailValues: { owner: risk.ownerName },
      href: `/risk-register?open=${risk.id}`,
    });
  }

  for (const analysis of analyses) {
    if (analysis.status !== "processing" && analysis.status !== "queued") continue;
    items.push({
      id: `analysis-${analysis.id}`,
      icon: ClipboardList,
      tone: "warning",
      titleKey: "assessmentIncomplete",
      titleValues: { name: analysis.title },
      detailKey: "assessmentIncompleteDetail",
      detailValues: {
        owner: analysis.requestedByName,
        updated: formatRelativeTime(analysis.updatedAt, locale),
      },
      href: `/analysis?doc=${analysis.documentId}`,
    });
  }

  const rank: Record<Tone, number> = { danger: 0, warning: 1, accent: 2, success: 3, neutral: 4 };
  return items.sort((a, b) => rank[a.tone] - rank[b.tone]);
}
