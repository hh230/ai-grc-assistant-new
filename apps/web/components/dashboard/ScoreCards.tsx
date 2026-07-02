"use client";

import { ShieldCheck, Activity } from "lucide-react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { TrendPill } from "@/components/ui/TrendPill";
import { Badge } from "@/components/ui/Badge";
import { COMPLIANCE_SCORE, RISK_SCORE } from "@/lib/data";

export function ScoreCards() {
  const t = useTranslations("dashboard.scoreCards");

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      {/* Overall Compliance Score */}
      <Card grain className="flex items-center gap-6">
        <ScoreRing value={COMPLIANCE_SCORE.value} caption={t("scoreCaption")} tone="success" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-success" strokeWidth={1.75} />
            <span className="text-sm font-medium text-foreground-secondary">
              {t("complianceTitle")}
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-medium tabular-nums text-foreground">
              {COMPLIANCE_SCORE.value}
              <span className="text-base text-foreground-muted">/100</span>
            </span>
            <TrendPill
              trend={COMPLIANCE_SCORE.trend}
              value={COMPLIANCE_SCORE.delta}
              goodWhen="up"
            />
          </div>
          <p className="mt-1.5 text-xs text-foreground-muted">{t("complianceCaption")}</p>
          <div className="mt-4 flex items-center gap-2">
            <Badge tone="success" dot>
              {t("onTrack")}
            </Badge>
            <span className="text-2xs text-foreground-muted">
              {t("target", { value: COMPLIANCE_SCORE.target })}
            </span>
          </div>
        </div>
      </Card>

      {/* Overall Risk Score */}
      <Card grain className="flex items-center gap-6">
        <ScoreRing value={RISK_SCORE.value} caption={t("indexCaption")} tone="warning" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-warning" strokeWidth={1.75} />
            <span className="text-sm font-medium text-foreground-secondary">
              {t("riskTitle")}
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-mono text-2xl font-medium tabular-nums text-foreground">
              {RISK_SCORE.value}
              <span className="text-base text-foreground-muted">/100</span>
            </span>
            <TrendPill trend={RISK_SCORE.trend} value={RISK_SCORE.delta} goodWhen="down" />
          </div>
          <p className="mt-1.5 text-xs text-foreground-muted">{t("riskCaption")}</p>
          <div className="mt-4 flex items-center gap-2">
            <Badge tone="warning" dot>
              {t("riskBand")}
            </Badge>
            <span className="text-2xs text-foreground-muted">{t("improvingQoQ")}</span>
          </div>
        </div>
      </Card>
    </div>
  );
}
