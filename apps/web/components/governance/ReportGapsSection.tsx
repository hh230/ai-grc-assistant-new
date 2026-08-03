"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle, TrendingDown } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge, type Tone } from "@/components/ui/Badge";
import type { GovernanceReportTopRisk } from "@/lib/planGeneration/types";

const SEVERITY_TONE: Record<string, Tone> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
};

/**
 * Sections 3 & 4 (ADR 0066 §4): "Gap" (fact) and "Impact" (consequence) are different claims,
 * kept as visually distinct blocks rather than one technical bullet — reads as a real consulting
 * deliverable, not a to-do list. Both read the same `topRisks[]`, paired by list order.
 */
export function CriticalGapsSection({ topRisks }: { topRisks: GovernanceReportTopRisk[] }) {
  const t = useTranslations("governanceReport");
  if (topRisks.length === 0) return null;
  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-danger" strokeWidth={1.75} />
        <h3 className="text-sm font-medium text-foreground">{t("criticalGaps.title")}</h3>
      </div>
      <ul className="space-y-2.5">
        {topRisks.map((risk) => (
          <li
            key={risk.gapId}
            className="flex items-start justify-between gap-3 rounded-lg border border-hairline px-3.5 py-2.5 text-sm"
          >
            <span className="text-foreground-secondary">{risk.description}</span>
            <Badge tone={SEVERITY_TONE[risk.severity] ?? "neutral"} className="shrink-0">
              {t.has(`severity.${risk.severity}` as never)
                ? t(`severity.${risk.severity}` as never)
                : risk.severity}
            </Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function BusinessImpactSection({ topRisks }: { topRisks: GovernanceReportTopRisk[] }) {
  const t = useTranslations("governanceReport");
  if (topRisks.length === 0) return null;
  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <TrendingDown className="h-4 w-4 text-danger" strokeWidth={1.75} />
        <h3 className="text-sm font-medium text-foreground">{t("businessImpact.title")}</h3>
      </div>
      <ul className="space-y-2.5 text-sm text-foreground-secondary">
        {topRisks.map((risk) => (
          <li key={risk.gapId} className="rounded-lg border border-hairline px-3.5 py-2.5">
            {risk.impact}
          </li>
        ))}
      </ul>
    </Card>
  );
}
