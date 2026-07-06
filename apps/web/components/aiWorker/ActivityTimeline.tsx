"use client";

import { useLocale, useTranslations } from "next-intl";
import { History } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useWorkerEvents } from "@/hooks/useKnowledgeWorker";
import { formatRelativeTime } from "@/lib/dashboard/relativeTime";
import type { AppLocale } from "@/i18n/routing";
import { toneIconClasses } from "@/lib/design/tone";
import { cn } from "@/lib/utils";
import { EVENT_META } from "./eventMeta";

export function ActivityTimeline() {
  const t = useTranslations("aiWorkerWorkspace.timeline");
  const locale = useLocale() as AppLocale;
  const { data: events, isLoading } = useWorkerEvents(50);

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description")} />

      {isLoading ? (
        <div className="mt-5 space-y-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : !events || events.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-elevated">
            <History className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
          </div>
          <p className="text-sm font-medium text-foreground">{t("emptyTitle")}</p>
        </div>
      ) : (
        <ol className="mt-5 max-h-[28rem] space-y-1 overflow-y-auto">
          {events.map((event, index) => {
            const meta = EVENT_META[event.eventType];
            const Icon = meta.icon;
            const isLast = index === events.length - 1;
            return (
              <li key={event.id} className="relative flex gap-3.5 pb-4 last:pb-0">
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
                  <p className="text-sm leading-snug text-foreground-secondary">{event.message}</p>
                  <p className="mt-0.5 text-2xs text-foreground-muted">
                    {formatRelativeTime(event.occurredAt, locale)}
                    {event.actorUserId && ` · ${event.actorUserId}`}
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
