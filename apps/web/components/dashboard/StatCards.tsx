"use client";

import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { TrendPill } from "@/components/ui/TrendPill";
import { KPIS } from "@/lib/data";

export function StatCards() {
  const t = useTranslations("dashboard.kpis");

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {KPIS.map((kpi) => (
        <Card key={kpi.labelKey} className="p-4">
          <p className="text-xs text-foreground-muted">{t(`${kpi.labelKey}.label`)}</p>
          <div className="mt-2 flex items-baseline justify-between gap-2">
            <span className="font-mono text-xl font-medium tabular-nums tracking-tight text-foreground">
              {kpi.value}
            </span>
            {kpi.trend !== "flat" && (
              <TrendPill
                trend={kpi.trend}
                value={kpi.delta}
                goodWhen={kpi.labelKey === "openFindings" ? "down" : "up"}
              />
            )}
          </div>
          <p className="mt-1 text-2xs text-foreground-muted">{t(`${kpi.labelKey}.sub`)}</p>
        </Card>
      ))}
    </div>
  );
}
