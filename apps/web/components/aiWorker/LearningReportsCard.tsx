"use client";

import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useLearningReports } from "@/hooks/useKnowledgeWorker";
import type { LearningReports } from "@/lib/knowledgeWorker/types";

const STAT_KEYS: (keyof LearningReports)[] = [
  "totalItems",
  "addedThisCycle",
  "updated",
  "needsReview",
  "verified",
  "outdated",
];

export function LearningReportsCard() {
  const t = useTranslations("aiWorkerWorkspace.reports");
  const { data: reports, isLoading } = useLearningReports();

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description")} />

      <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
        {isLoading || !reports
          ? Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-16" />)
          : STAT_KEYS.map((key) => (
              <div key={key} className="rounded-xl border border-hairline bg-surface/60 p-4">
                <p className="text-2xs text-foreground-muted">{t(`stats.${key}`)}</p>
                <p className="mt-1.5 font-mono text-xl font-medium tabular-nums tracking-tight text-foreground">
                  {reports[key]}
                </p>
              </div>
            ))}
      </div>
    </Card>
  );
}
