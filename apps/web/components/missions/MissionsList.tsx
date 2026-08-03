"use client";

import { useLocale, useTranslations } from "next-intl";
import { ArrowRight, Loader2, TriangleAlert, Workflow } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Link } from "@/i18n/navigation";
import { useMissions } from "@/hooks/useMissions";
import { formatRelativeTime } from "@/lib/dashboard/relativeTime";
import type { AppLocale } from "@/i18n/routing";
import { isMissionStatus, type Mission, type MissionStatus } from "@/lib/missions/types";

const STATUS_TONE: Record<MissionStatus, Tone> = {
  planned: "neutral",
  executing: "accent",
  completed: "success",
  failed: "danger",
  cancelled: "neutral",
};

function StatusBadge({ status, awaitingApproval }: { status: string; awaitingApproval: boolean }) {
  const t = useTranslations("missionsPage");
  if (awaitingApproval) {
    return (
      <Badge tone="warning" dot>
        {t("status.awaitingApproval")}
      </Badge>
    );
  }
  const tone = isMissionStatus(status) ? STATUS_TONE[status] : "neutral";
  const label = isMissionStatus(status) ? t(`status.${status}`) : status;
  return <Badge tone={tone}>{label}</Badge>;
}

function MissionRow({ mission }: { mission: Mission }) {
  const t = useTranslations("missionsPage");
  const locale = useLocale() as AppLocale;
  return (
    <tr className="border-b border-hairline last:border-0">
      <td className="px-5 py-3">
        <p className="truncate font-medium text-foreground">{mission.goal}</p>
        <p className="mt-0.5 truncate text-2xs text-foreground-muted">{mission.agent}</p>
      </td>
      <td className="px-3 py-3">
        <StatusBadge status={mission.status} awaitingApproval={mission.awaitingApproval} />
      </td>
      <td className="px-3 py-3 text-foreground-secondary">
        {mission.lastStep
          ? t("stepsProgress", { count: mission.stepCount, lastStep: mission.lastStep })
          : t("noSteps")}
      </td>
      <td className="px-3 py-3 text-foreground-secondary">{mission.createdByName}</td>
      <td className="px-3 py-3 text-foreground-secondary">
        {formatRelativeTime(mission.updatedAt, locale)}
      </td>
    </tr>
  );
}

export function MissionsList() {
  const t = useTranslations("missionsPage");
  const { data: missions, isLoading, isError } = useMissions();

  if (isLoading) {
    return (
      <Card className="flex items-center justify-center gap-2 py-12 text-sm text-foreground-muted">
        <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
        {t("loading")}
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <div className="flex items-start gap-2 text-sm text-danger">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.75} />
          <span>{t("loadError")}</span>
        </div>
      </Card>
    );
  }

  if (!missions || missions.length === 0) {
    return (
      <Card grain className="flex flex-col items-center gap-4 py-16 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
          <Workflow className="h-5 w-5 text-accent-foreground" strokeWidth={1.75} />
        </div>
        <div className="max-w-sm space-y-1.5">
          <p className="text-sm font-medium text-foreground">{t("emptyState.title")}</p>
          <p className="text-xs text-foreground-muted">{t("emptyState.description")}</p>
        </div>
        <Link
          href="/upload"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
        >
          {t("emptyState.cta")}
          <ArrowRight className="h-4 w-4" strokeWidth={2} />
        </Link>
      </Card>
    );
  }

  return (
    <Card flush>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-hairline text-start text-2xs uppercase tracking-wider text-foreground-muted">
              <th className="px-5 py-2.5 font-medium">{t("table.mission")}</th>
              <th className="px-3 py-2.5 font-medium">{t("table.status")}</th>
              <th className="px-3 py-2.5 font-medium">{t("table.progress")}</th>
              <th className="px-3 py-2.5 font-medium">{t("table.owner")}</th>
              <th className="px-3 py-2.5 font-medium">{t("table.updated")}</th>
            </tr>
          </thead>
          <tbody>
            {missions.map((mission) => (
              <MissionRow key={mission.id} mission={mission} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
