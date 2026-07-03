"use client";

import { useTranslations } from "next-intl";
import { BookMarked, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type { Priority, Recommendation } from "@/lib/analysis/types";

const PRIORITY_TONE: Record<Priority, "danger" | "warning" | "accent"> = {
  high: "danger",
  medium: "warning",
  low: "accent",
};

export function Recommendations({ recommendations }: { recommendations: Recommendation[] }) {
  const t = useTranslations("recommendations");
  if (recommendations.length === 0) return null;

  return (
    <Card flush>
      <div className="px-5 pt-4">
        <SectionHeader
          title={t("title")}
          description={t("description", { count: recommendations.length })}
        />
      </div>
      <div className="mt-3 divide-y divide-hairline">
        {recommendations.map((rec, i) => (
          <div key={i} className="px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-medium text-foreground">{rec.change}</p>
              <Badge tone={PRIORITY_TONE[rec.priority]} className="shrink-0">
                {t(`priority.${rec.priority}`)}
              </Badge>
            </div>
            <p className="mt-1.5 text-xs text-foreground-secondary">
              <span className="font-medium text-foreground-secondary">{t("reasonLabel")}</span>{" "}
              {rec.reason}
            </p>
            {rec.expectedImpact && (
              <p className="mt-1 text-xs text-foreground-secondary">
                <span className="font-medium text-foreground-secondary">{t("impactLabel")}</span>{" "}
                {rec.expectedImpact}
              </p>
            )}
            {(rec.relatedFramework || rec.reference) && (
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-foreground-muted">
                {rec.relatedFramework && (
                  <span className="inline-flex items-center gap-1.5">
                    <ShieldCheck className="h-3 w-3" strokeWidth={1.75} />
                    {rec.relatedFramework}
                  </span>
                )}
                {rec.reference && (
                  <span className="inline-flex items-center gap-1.5">
                    <BookMarked className="h-3 w-3" strokeWidth={1.75} />
                    {rec.reference}
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
