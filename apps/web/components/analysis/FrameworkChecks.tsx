"use client";

import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ProgressBar } from "@/components/ui/ProgressBar";
import type { Alignment, FrameworkCoverage } from "@/lib/analysis/types";
import { cn } from "@/lib/utils";

const ALIGNMENT_META: Record<
  Alignment,
  { dot: string; value: number; tone: "success" | "warning" | "danger" | "accent" }
> = {
  strong: { dot: "bg-success", value: 100, tone: "success" },
  partial: { dot: "bg-warning", value: 55, tone: "warning" },
  gap: { dot: "bg-danger", value: 15, tone: "danger" },
  unknown: { dot: "bg-foreground-muted", value: 40, tone: "accent" },
};

export function FrameworkChecks({ frameworks }: { frameworks: FrameworkCoverage[] }) {
  const t = useTranslations("frameworkChecks");
  if (frameworks.length === 0) return null;

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description")} />
      <div className="mt-4 space-y-4">
        {frameworks.map((fw) => {
          const meta = ALIGNMENT_META[fw.alignment];
          return (
            <div key={fw.framework} className="space-y-1.5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-foreground">{fw.framework}</p>
                <span className="inline-flex shrink-0 items-center gap-1.5 text-2xs text-foreground-secondary">
                  <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
                  {t(`alignment.${fw.alignment}`)}
                </span>
              </div>
              <ProgressBar value={meta.value} tone={meta.tone} />
              <p className="text-xs text-foreground-muted">{fw.assessment}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
