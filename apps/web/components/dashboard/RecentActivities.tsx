import {
  ClipboardCheck,
  FileCheck2,
  TriangleAlert,
  Sparkles,
  FileUp,
  History,
  type LucideIcon,
} from "lucide-react";
import { getTranslations, getLocale } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Link } from "@/i18n/navigation";
import { getActor } from "@/lib/auth/actor";
import { getRecentActivity, type ActivityKind } from "@/lib/dashboard/activity";
import { formatRelativeTime } from "@/lib/dashboard/relativeTime";
import type { AppLocale } from "@/i18n/routing";
import { cn } from "@/lib/utils";
import { toneIconClasses, type Tone } from "@/lib/design/tone";

const kindMeta: Record<ActivityKind, { icon: LucideIcon; tone: Tone }> = {
  document: { icon: FileUp, tone: "neutral" },
  analysis: { icon: Sparkles, tone: "accent" },
  analysisFailed: { icon: TriangleAlert, tone: "danger" },
  policy: { icon: FileCheck2, tone: "accent" },
  risk: { icon: ClipboardCheck, tone: "success" },
};

export async function RecentActivities() {
  const t = await getTranslations("dashboard.recentActivities");
  const locale = (await getLocale()) as AppLocale;
  const actor = await getActor();
  const items = actor ? await getRecentActivity(actor) : [];

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description")} />

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-elevated">
            <History className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">{t("emptyTitle")}</p>
            <p className="max-w-xs text-xs text-foreground-muted">{t("emptyDescription")}</p>
          </div>
        </div>
      ) : (
        <ol className="mt-5 space-y-1">
          {items.map((activity, index) => {
            const meta = kindMeta[activity.kind];
            const Icon = meta.icon;
            const isLast = index === items.length - 1;
            return (
              <li key={activity.id} className="relative flex gap-3.5 pb-4 last:pb-0">
                {!isLast && (
                  <span
                    className="absolute start-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-hairline"
                    aria-hidden
                  />
                )}
                <span
                  className={cn(
                    "relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                    toneIconClasses[meta.tone],
                  )}
                >
                  <Icon className="h-4 w-4" strokeWidth={1.75} />
                </span>
                <div className="min-w-0 flex-1 pt-1">
                  <Link
                    href={activity.href}
                    className="text-sm leading-snug text-foreground-secondary hover:text-foreground"
                  >
                    <span className="font-medium text-foreground">{activity.actorName}</span>{" "}
                    {t(`actions.${activity.actionKey}`)}{" "}
                    <span className="text-foreground">{activity.targetName}</span>
                  </Link>
                  <p className="mt-0.5 text-2xs text-foreground-muted">
                    {formatRelativeTime(activity.time, locale)}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
