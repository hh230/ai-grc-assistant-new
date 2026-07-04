import { ShieldCheck, Activity } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { TrendPill } from "@/components/ui/TrendPill";
import { Badge } from "@/components/ui/Badge";
import { getActor } from "@/lib/auth/actor";
import { getDashboardMetrics, type DashboardRangeDays } from "@/lib/dashboard/metrics";

export async function ScoreCards({ rangeDays }: { rangeDays: DashboardRangeDays }) {
  const t = await getTranslations("dashboard.scoreCards");
  const actor = await getActor();
  if (!actor) return null;

  const metrics = await getDashboardMetrics(actor, rangeDays);
  const hasData = metrics.documentsAnalyzedCount > 0;
  const complianceValue = metrics.complianceScore ?? 0;
  const riskValue = metrics.riskScore ?? 0;

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      {/* Compliance Level */}
      <Card grain className="flex items-center gap-6">
        <ScoreRing value={complianceValue} caption={t("scoreCaption")} tone="success" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-success" strokeWidth={1.75} />
            <span className="text-sm font-medium text-foreground-secondary">
              {t("complianceTitle")}
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-medium tabular-nums text-foreground">
              {complianceValue}
              <span className="text-base text-foreground-muted">/100</span>
            </span>
            {metrics.complianceTrend && (
              <TrendPill
                trend={metrics.complianceTrend.direction}
                value={Math.abs(metrics.complianceTrend.delta)}
                goodWhen="up"
              />
            )}
          </div>
          <p className="mt-1.5 text-xs text-foreground-muted">
            {hasData
              ? t(`recommendation.${metrics.complianceBand}`)
              : t("noDataYet")}
          </p>
          {hasData && (
            <div className="mt-4 flex items-center gap-2">
              <Badge
                tone={
                  metrics.complianceBand === "high"
                    ? "success"
                    : metrics.complianceBand === "medium"
                      ? "warning"
                      : "danger"
                }
                dot
              >
                {t(`band.${metrics.complianceBand}`)}
              </Badge>
              <span className="text-2xs text-foreground-muted">
                {t("documentsAnalyzed", { count: metrics.documentsAnalyzedCount })}
              </span>
            </div>
          )}
        </div>
      </Card>

      {/* Risk Level */}
      <Card grain className="flex items-center gap-6">
        <ScoreRing value={riskValue} caption={t("indexCaption")} tone="warning" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-warning" strokeWidth={1.75} />
            <span className="text-sm font-medium text-foreground-secondary">
              {t("riskTitle")}
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-medium tabular-nums text-foreground">
              {riskValue}
              <span className="text-base text-foreground-muted">/100</span>
            </span>
            {metrics.riskTrend && (
              <TrendPill
                trend={metrics.riskTrend.direction}
                value={Math.abs(metrics.riskTrend.delta)}
                goodWhen="down"
              />
            )}
          </div>
          <p className="mt-1.5 text-xs text-foreground-muted">
            {hasData ? t("riskCaption") : t("noDataYet")}
          </p>
          {hasData && (
            <div className="mt-4 flex items-center gap-2">
              <Badge
                tone={
                  metrics.riskBand === "low"
                    ? "success"
                    : metrics.riskBand === "medium"
                      ? "warning"
                      : "danger"
                }
                dot
              >
                {t(`riskBandLabel.${metrics.riskBand}`)}
              </Badge>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
