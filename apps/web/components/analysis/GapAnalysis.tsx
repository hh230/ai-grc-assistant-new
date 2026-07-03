"use client";

import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type { Gap, Severity } from "@/lib/analysis/types";
import { cn } from "@/lib/utils";

const SEVERITY_RAIL: Record<Severity, string> = {
  high: "bg-danger",
  medium: "bg-warning",
  low: "bg-accent",
  info: "bg-foreground-muted",
};

export function GapAnalysis({ gaps }: { gaps: Gap[] }) {
  const t = useTranslations("gapAnalysis");
  if (gaps.length === 0) return null;

  return (
    <Card flush>
      <div className="px-5 pt-4">
        <SectionHeader title={t("title")} description={t("description", { count: gaps.length })} />
      </div>
      <div className="mt-3 divide-y divide-hairline">
        {gaps.map((gap, i) => (
          <div key={i} className="relative flex gap-3 px-5 py-3.5">
            <span className={cn("w-0.5 shrink-0 rounded-full", SEVERITY_RAIL[gap.severity])} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground">{gap.area}</p>
              <p className="mt-1 text-xs text-foreground-secondary">{gap.description}</p>
              {gap.framework && (
                <p className="mt-1.5 text-2xs text-foreground-muted">
                  {t("relatesTo", { framework: gap.framework })}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
