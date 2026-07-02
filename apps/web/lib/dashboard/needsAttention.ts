import { Library, TriangleAlert, ClipboardList, type LucideIcon } from "lucide-react";
import { ACTIVE_FRAMEWORKS, RECENT_ASSESSMENTS, RISK_DISTRIBUTION } from "@/lib/data";
import { FRAMEWORKS } from "@/lib/frameworks/catalog";
import type { Tone } from "@/lib/design/tone";

export interface NeedsAttentionItem {
  id: string;
  icon: LucideIcon;
  tone: Tone;
  titleKey: string;
  /** Values for the title interpolation; `categoryKey` (if present) must be resolved via
   * the `dashboard.riskDistribution.categories` namespace before use as `category`. */
  titleValues: Record<string, string | number>;
  categoryKey?: string;
  detailKey: string;
  detailValues: Record<string, string | number>;
  href: string;
}

/**
 * Band 2 of the dashboard (V2-P3 design proposal §11) — "what needs my attention?".
 * Deliberately derived from the same typed demo arrays the rest of the dashboard already
 * renders (ACTIVE_FRAMEWORKS, RISK_DISTRIBUTION, RECENT_ASSESSMENTS) rather than a new,
 * parallel dataset: frameworks not yet compliant, risk categories in the danger/warning
 * band, and assessments still awaiting completion. Ranked danger-first, then warning.
 */
export function getNeedsAttentionItems(): NeedsAttentionItem[] {
  const items: NeedsAttentionItem[] = [];

  // ACTIVE_FRAMEWORKS is illustrative dashboard data and includes frameworks (e.g. PDPL)
  // that aren't yet in the real control catalog — only link to /frameworks/[id] when that
  // detail page will actually resolve, otherwise fall back to the frameworks index.
  const knownFrameworkIds = new Set(FRAMEWORKS.map((f) => f.id));
  for (const framework of ACTIVE_FRAMEWORKS) {
    if (framework.status === "compliant") continue;
    items.push({
      id: `framework-${framework.id}`,
      icon: Library,
      tone: framework.status === "at_risk" ? "danger" : "warning",
      titleKey: "frameworkGap",
      titleValues: { code: framework.code },
      detailKey: "frameworkGapDetail",
      detailValues: {
        coverage: framework.coverage,
        remaining: framework.controls - framework.controlsMet,
      },
      href: knownFrameworkIds.has(framework.id) ? `/frameworks/${framework.id}` : "/frameworks",
    });
  }

  for (const slice of RISK_DISTRIBUTION) {
    if (slice.tone !== "danger" && slice.tone !== "warning") continue;
    items.push({
      id: `risk-${slice.label}`,
      icon: TriangleAlert,
      tone: slice.tone,
      titleKey: "riskExposure",
      titleValues: {},
      categoryKey: slice.labelKey,
      detailKey: "riskExposureDetail",
      detailValues: { value: slice.value },
      href: "/risk-register",
    });
  }

  for (const assessment of RECENT_ASSESSMENTS) {
    if (assessment.status !== "in_progress") continue;
    items.push({
      id: `assessment-${assessment.id}`,
      icon: ClipboardList,
      tone: "warning",
      titleKey: "assessmentIncomplete",
      titleValues: { name: assessment.name },
      detailKey: "assessmentIncompleteDetail",
      detailValues: { owner: assessment.owner, updated: assessment.updated },
      href: "/assessments",
    });
  }

  const rank: Record<Tone, number> = { danger: 0, warning: 1, accent: 2, success: 3, neutral: 4 };
  return items.sort((a, b) => rank[a.tone] - rank[b.tone]);
}
