import { getLocale, getTranslations } from "next-intl/server";
import { CheckCircle2, CalendarClock, ClipboardCheck, FileCheck, Paperclip } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { formatRelativeTime } from "@/lib/dashboard/relativeTime";
import type { AppLocale } from "@/i18n/routing";
import type { GovernanceEvent, GovernanceEventKind } from "@/lib/dashboard/governanceActivity";

/**
 * Section 4 — what has actually happened to the program.
 *
 * Five event kinds and no sixth without answering the pillar-10 question. A feed that also carried
 * logins and page views would train the customer to stop reading the one place that records a
 * governance decision.
 */
const ICON: Record<GovernanceEventKind, typeof CheckCircle2> = {
  assessmentCompleted: ClipboardCheck,
  planApproved: FileCheck,
  actionCompleted: CheckCircle2,
  evidenceAdded: Paperclip,
  reviewDue: CalendarClock,
};

export async function GovernanceActivity({ events }: { events: GovernanceEvent[] }) {
  const t = await getTranslations("governanceActivity");
  const locale = (await getLocale()) as AppLocale;

  if (events.length === 0) return null;

  return (
    <Card grain>
      <SectionHeader title={t("title")} description={t("description")} />
      <ul className="mt-3.5 space-y-1">
        {events.map((event) => {
          const Icon = ICON[event.kind];
          return (
            <li
              key={event.id}
              className="flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm odd:bg-surface"
            >
              <span className="flex min-w-0 items-center gap-2.5">
                <Icon
                  className="h-3.5 w-3.5 shrink-0 text-foreground-muted"
                  strokeWidth={1.75}
                  aria-hidden
                />
                <span className="truncate text-foreground-secondary">
                  {t(`kind.${event.kind}`)}
                  {event.subject && (
                    <span className="text-foreground-muted"> · {event.subject}</span>
                  )}
                </span>
              </span>
              <span className="shrink-0 text-2xs text-foreground-muted">
                {formatRelativeTime(event.occurredAt, locale)}
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
