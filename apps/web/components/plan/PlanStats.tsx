"use client";

import { useTranslations } from "next-intl";
import { CheckCircle2, ClipboardList, Flame, Target } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import type { PlanItem, Priority } from "@/lib/planExecution/types";

const NOW_SECONDS = () => Date.now() / 1000;

interface PlanStatsProps {
  items: PlanItem[];
}

/** The "how is the program actually going" scoreboard — completion, overdue count, and the
 * single next thing to do, ahead of the full item list (professional-program feel, not a bare
 * to-do count). */
export function PlanStats({ items }: PlanStatsProps) {
  const t = useTranslations("planExecution");
  const total = items.length;
  const done = items.filter((item) => item.status === "done").length;
  const now = NOW_SECONDS();
  const overdue = items.filter(
    (item) => item.status !== "done" && item.dueAt != null && item.dueAt < now,
  ).length;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;

  const priorityRank: Record<Priority, number> = { critical: 0, high: 1, medium: 2, low: 3 };
  const nextUp = [...items]
    .filter((item) => item.status !== "done")
    .sort((a, b) => {
      const byPriority = priorityRank[a.priority] - priorityRank[b.priority];
      if (byPriority !== 0) return byPriority;
      return (a.dueAt ?? Infinity) - (b.dueAt ?? Infinity);
    })[0];

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <Card>
        <div className="flex items-center gap-2 text-foreground-muted">
          <CheckCircle2 className="h-4 w-4" strokeWidth={1.75} />
          <span className="text-2xs uppercase tracking-wider">{t("stats.completion")}</span>
        </div>
        <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">{percent}%</p>
        <p className="mt-1 text-2xs text-foreground-muted">
          {t("stats.itemsDone", { done, total })}
        </p>
        <ProgressBar value={percent} tone="success" className="mt-3" />
      </Card>
      <Card>
        <div className="flex items-center gap-2 text-foreground-muted">
          <Flame className="h-4 w-4" strokeWidth={1.75} />
          <span className="text-2xs uppercase tracking-wider">{t("stats.overdue")}</span>
        </div>
        <p
          className={`mt-2 text-3xl font-semibold tracking-tight ${overdue > 0 ? "text-danger" : "text-foreground"}`}
        >
          {overdue}
        </p>
        <p className="mt-1 text-2xs text-foreground-muted">
          {overdue > 0 ? t("stats.overdueHint") : t("stats.onTrack")}
        </p>
      </Card>
      <Card>
        <div className="flex items-center gap-2 text-foreground-muted">
          <Target className="h-4 w-4" strokeWidth={1.75} />
          <span className="text-2xs uppercase tracking-wider">{t("stats.nextUp")}</span>
        </div>
        {nextUp ? (
          <p className="mt-2 line-clamp-2 text-sm font-medium leading-snug text-foreground">
            {nextUp.title}
          </p>
        ) : (
          <p className="mt-2 flex items-center gap-1.5 text-sm text-success">
            <ClipboardList className="h-4 w-4" strokeWidth={1.75} />
            {t("stats.allDone")}
          </p>
        )}
      </Card>
    </div>
  );
}
