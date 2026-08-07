import { getFormatter, getTranslations } from "next-intl/server";
import { ArrowRight, CalendarClock } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Link } from "@/i18n/navigation";
import type { ProgramStatus as Status } from "@/lib/dashboard/programStatus";

/**
 * Section 1 — the head of the home page (CLAUDE.md §3 pillar 10).
 *
 * The customer's first question is "where am I now?", not "what is my score". So this states which
 * program they are running, when it was assessed, when it must be reviewed, and whether it is
 * still standing — before any measurement appears anywhere on the page.
 *
 * With no program it is the ENTIRE page: a dashboard of zeroes is not an empty dashboard, it is a
 * customer who has not started, and the only useful thing to show them is the way in.
 */
/** A date, not a timestamp. Declared inline rather than as a named next-intl format because a
 * name that the locale config does not define silently degrades to a full `toString()`. */
const DATE_ONLY = { year: "numeric", month: "short", day: "numeric" } as const;

export async function ProgramStatus({ status }: { status: Status }) {
  const t = await getTranslations("programStatus");
  const format = await getFormatter();

  if (status.state === "none") {
    return (
      <Card grain className="px-6 py-8">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">{t("none.title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-foreground-secondary">{t("none.description")}</p>
        <ol className="mt-5 flex flex-wrap items-center gap-2 text-2xs">
          {(["discovery", "report", "plan"] as const).map((step, index) => (
            <li key={step} className="flex items-center gap-2">
              {index > 0 && (
                <ArrowRight
                  className="h-3 w-3 text-foreground-muted"
                  strokeWidth={2}
                  aria-hidden
                />
              )}
              <span
                className={
                  index === 0
                    ? "rounded-full border border-accent/40 bg-accent-soft px-3 py-1 text-accent-foreground"
                    : "rounded-full border border-hairline px-3 py-1 text-foreground-muted"
                }
              >
                {t(`none.step.${step}`)}
              </span>
            </li>
          ))}
        </ol>
        <Link
          href="/discovery"
          className="mt-6 inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
        >
          {t("none.cta")}
          <ArrowRight className="h-4 w-4" strokeWidth={2} />
        </Link>
      </Card>
    );
  }

  const assessedAt = status.assessedAt ? new Date(status.assessedAt) : null;
  const reviewDueAt = status.reviewDueAt ? new Date(status.reviewDueAt) : null;

  return (
    <Card className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <div className="flex items-center gap-2.5">
          <h1 className="text-lg font-semibold tracking-tight text-foreground">{t("title")}</h1>
          <Badge tone={status.state === "reviewDue" ? "warning" : "success"} dot>
            {t(`state.${status.state}`)}
          </Badge>
        </div>
        <p className="mt-1.5 text-sm text-foreground-secondary">
          {t("version", { version: status.version ?? 0 })}
          {assessedAt && ` · ${t("assessed", { date: format.dateTime(assessedAt, DATE_ONLY) })}`}
        </p>
      </div>

      {reviewDueAt && (
        <div className="flex items-start gap-2 text-2xs text-foreground-muted">
          <CalendarClock className="mt-px h-3.5 w-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
          <span>
            {/* Stated as a date AND as a distance: the date is the fact, the distance is what makes
                it act-on-able. */}
            {t("review", { date: format.dateTime(reviewDueAt, DATE_ONLY) })}
            <br />
            {status.state === "reviewDue"
              ? t("reviewOverdue", { days: Math.abs(status.daysUntilReview ?? 0) })
              : t("reviewIn", { days: status.daysUntilReview ?? 0 })}
          </span>
        </div>
      )}
    </Card>
  );
}
