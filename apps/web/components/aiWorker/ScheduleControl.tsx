"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { useUpdateWorkerSchedule, useWorkerStatus } from "@/hooks/useKnowledgeWorker";
import { cn } from "@/lib/utils";

export function ScheduleControl() {
  const t = useTranslations("aiWorkerWorkspace.schedule");
  const { data: status } = useWorkerStatus();
  const mutation = useUpdateWorkerSchedule();
  const [intervalHours, setIntervalHours] = useState("12");

  useEffect(() => {
    if (status) setIntervalHours(String(status.intervalHours));
    // Deliberately keyed on the interval value alone, not the whole `status` object: the
    // 15s status poll returns a new object identity every time, and syncing on every poll
    // would blow away whatever the admin is mid-typing in the interval input below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.intervalHours]);

  if (!status) return null;

  const intervalChanged = Number(intervalHours) !== status.intervalHours;

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description")} />

      <div className="mt-5 flex flex-wrap items-center gap-6">
        <label className="flex items-center gap-3">
          <button
            type="button"
            role="switch"
            aria-checked={status.enabled}
            onClick={() => mutation.mutate({ enabled: !status.enabled })}
            disabled={mutation.isPending}
            className={cn(
              "relative h-6 w-11 shrink-0 rounded-full transition-colors",
              status.enabled ? "bg-success" : "bg-surface-elevated border border-hairline",
            )}
          >
            <span
              className={cn(
                "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-soft transition-transform",
                status.enabled ? "translate-x-5 rtl:-translate-x-5" : "translate-x-0.5",
              )}
            />
          </button>
          <span className="text-sm text-foreground-secondary">
            {status.enabled ? t("enabled") : t("disabled")}
          </span>
        </label>

        <div className="flex items-center gap-2">
          <label htmlFor="interval-hours" className="text-sm text-foreground-secondary">
            {t("intervalLabel")}
          </label>
          <input
            id="interval-hours"
            type="number"
            min={1}
            step={1}
            value={intervalHours}
            onChange={(event) => setIntervalHours(event.target.value)}
            className="h-9 w-20 rounded-lg border border-hairline bg-surface/60 px-2.5 text-sm text-foreground outline-none focus:border-hairline-strong"
          />
          <span className="text-sm text-foreground-muted">{t("hours")}</span>
          <button
            type="button"
            onClick={() => mutation.mutate({ intervalHours: Number(intervalHours) })}
            disabled={!intervalChanged || mutation.isPending || Number(intervalHours) <= 0}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline-strong bg-surface-elevated px-3 text-sm font-medium text-foreground transition-colors hover:bg-surface disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {t("save")}
          </button>
        </div>
      </div>
    </Card>
  );
}
