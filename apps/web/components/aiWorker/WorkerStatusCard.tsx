"use client";

import { useLocale, useTranslations } from "next-intl";
import { Activity, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { useWorkerStatus } from "@/hooks/useKnowledgeWorker";
import { formatRelativeTime } from "@/lib/dashboard/relativeTime";
import type { AppLocale } from "@/i18n/routing";

export function WorkerStatusCard() {
  const t = useTranslations("aiWorkerWorkspace.status");
  const locale = useLocale() as AppLocale;
  const { data: status, isLoading } = useWorkerStatus();

  if (isLoading || !status) {
    return (
      <Card>
        <Skeleton className="h-24 w-full" />
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
            {t("eyebrow")}
          </p>
          <div className="mt-2 flex items-center gap-2">
            <Badge tone={status.running ? "success" : "neutral"} dot>
              {status.running ? t("running") : t("stopped")}
            </Badge>
            {status.currentCycle === "in_progress" && (
              <Badge tone="accent">
                <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
                {t("cycleInProgress")}
              </Badge>
            )}
          </div>
        </div>
        <Activity className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
      </div>

      {status.currentTask && (
        <p className="mt-3 text-sm text-foreground-secondary">
          <span className="font-medium text-foreground">{t("currentTask")}:</span>{" "}
          {status.currentTask}
        </p>
      )}

      <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <dt className="text-2xs text-foreground-muted">{t("interval")}</dt>
          <dd className="mt-1 text-sm font-medium text-foreground">
            {t("intervalHours", { hours: status.intervalHours })}
          </dd>
        </div>
        <div>
          <dt className="text-2xs text-foreground-muted">{t("lastRun")}</dt>
          <dd className="mt-1 text-sm font-medium text-foreground">
            {status.lastRunAt ? formatRelativeTime(status.lastRunAt, locale) : t("never")}
          </dd>
        </div>
        <div>
          <dt className="text-2xs text-foreground-muted">{t("nextRun")}</dt>
          <dd className="mt-1 text-sm font-medium text-foreground">
            {status.manualTriggerRequested
              ? t("manualTriggerPending")
              : status.nextRunAt
                ? formatRelativeTime(status.nextRunAt, locale)
                : t("dueNow")}
          </dd>
        </div>
        <div>
          <dt className="text-2xs text-foreground-muted">{t("lastRunReason")}</dt>
          <dd className="mt-1 text-sm font-medium text-foreground">
            {status.lastRunReason ? t(`reason.${status.lastRunReason}`) : "—"}
          </dd>
        </div>
      </dl>
    </Card>
  );
}
