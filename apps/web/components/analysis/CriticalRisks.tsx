"use client";

import { useTranslations } from "next-intl";
import { ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type { CriticalRisk, Severity } from "@/lib/analysis/types";
import { cn } from "@/lib/utils";

const SEVERITY_STYLES: Record<Severity, string> = {
  high: "bg-danger-soft text-danger",
  medium: "bg-warning-soft text-warning",
  low: "bg-accent-soft text-accent-foreground",
  info: "bg-surface-elevated text-foreground-muted",
};

export function CriticalRisks({ risks }: { risks: CriticalRisk[] }) {
  const t = useTranslations("criticalRisks");
  if (risks.length === 0) return null;

  return (
    <Card flush>
      <div className="px-5 pt-4">
        <SectionHeader title={t("title")} description={t("description", { count: risks.length })} />
      </div>
      <div className="mt-3 divide-y divide-hairline">
        {risks.map((risk, i) => (
          <div key={i} className="flex gap-3 px-5 py-3.5">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-danger" strokeWidth={1.75} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-foreground">{risk.title}</p>
                <span
                  className={cn(
                    "shrink-0 rounded-full px-2 py-0.5 text-2xs font-medium",
                    SEVERITY_STYLES[risk.severity],
                  )}
                >
                  {t(`severity.${risk.severity}`)}
                </span>
              </div>
              <p className="mt-1 text-xs text-foreground-secondary">{risk.detail}</p>
              <p className="mt-1.5 text-2xs text-foreground-muted">
                <span className="font-medium text-foreground-secondary">
                  {t("businessImpactLabel")}
                </span>{" "}
                {risk.businessImpact}
              </p>
              {risk.framework && (
                <p className="mt-1 text-2xs text-foreground-muted">
                  {t("relatesTo", { framework: risk.framework })}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
