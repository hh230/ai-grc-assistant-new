import { Sparkles } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { getActor } from "@/lib/auth/actor";
import { getDashboardMetrics, type DashboardRangeDays } from "@/lib/dashboard/metrics";

export async function ExecutiveSummary({ rangeDays }: { rangeDays: DashboardRangeDays }) {
  const t = await getTranslations("dashboard.executiveSummary");
  const actor = await getActor();
  if (!actor) return null;

  const metrics = await getDashboardMetrics(actor, rangeDays);
  const hasData = metrics.documentsAnalyzedCount > 0;

  const stats = [
    { key: "documentsAnalyzed", value: String(metrics.documentsAnalyzedCount) },
    { key: "frameworksAssessed", value: String(metrics.frameworksUsed.length) },
    { key: "identifiedGaps", value: String(metrics.topGaps.length) },
    { key: "highPriorityActions", value: String(metrics.topRecommendations.length) },
  ];

  return (
    <Card grain className="overflow-hidden">
      {/* Subtle accent fade at the top edge signals the AI-generated nature. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-accent-fade" />
      <div className="relative">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-soft">
              <Sparkles className="h-4 w-4 text-accent-foreground" strokeWidth={1.75} />
            </span>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">{t("title")}</h2>
          </div>
          <Badge tone="accent" dot>
            {t("aiGenerated")}
          </Badge>
        </div>

        <p className="mt-2 max-w-3xl text-xs text-foreground-muted">{t("description")}</p>

        {hasData ? (
          <>
            <p className="mt-4 max-w-3xl text-balance text-[15px] leading-relaxed text-foreground">
              {t("headline", {
                compliance: t(`complianceLabel.${metrics.complianceBand}`),
                risk: t(`riskLabel.${metrics.riskBand}`),
              })}
            </p>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-foreground-secondary">
              {t("body", {
                count: metrics.documentsAnalyzedCount,
                gaps: metrics.topGaps.length,
                recommendations: metrics.topRecommendations.length,
                frameworks: metrics.frameworksUsed.length,
              })}
            </p>
          </>
        ) : (
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-foreground-secondary">
            {t("emptyState")}
          </p>
        )}

        <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-hairline bg-hairline lg:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.key} className="bg-surface px-4 py-3.5">
              <p className="text-2xs uppercase tracking-wider text-foreground-muted">
                {t(`stats.${stat.key}`)}
              </p>
              <p className="mt-1 font-mono text-base font-medium tabular-nums text-foreground">
                {stat.value}
              </p>
            </div>
          ))}
        </div>

        <p className="mt-4 text-2xs text-foreground-muted">
          {t("footer", { count: metrics.documentsAnalyzedCount })}
        </p>
      </div>
    </Card>
  );
}
