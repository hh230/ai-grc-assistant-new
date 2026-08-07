import { getFormatter, getTranslations } from "next-intl/server";
import { ArrowRight, Zap } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Link } from "@/i18n/navigation";
import { PRIORITY_RANK, isQuickWin } from "@/lib/planExecution/grouping";
import type { PlanDetail, PlanItem } from "@/lib/planExecution/types";

/**
 * Section 3 — the largest card in the program experience, deliberately (CLAUDE.md §3 pillar 10).
 *
 * The product's whole claim is: do not only tell me where the problem is, tell me what to do
 * tomorrow. If a customer opens this page and cannot see their next three steps, the page has
 * failed however good the rest of it looks.
 *
 * No new ranking. Overdue first, then the plan's own priority order, then the nearest due date —
 * the same ordering the plan board already uses, so the home page never disagrees with the page it
 * summarises.
 */
const SHOWN = 3;

function nextActions(items: PlanItem[]): PlanItem[] {
  const now = Date.now();
  return items
    .filter((item) => item.status !== "done")
    .sort((a, b) => {
      const aOverdue = a.dueAt !== null && a.dueAt * 1000 < now;
      const bOverdue = b.dueAt !== null && b.dueAt * 1000 < now;
      if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;
      const byPriority = PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
      if (byPriority !== 0) return byPriority;
      return (a.dueAt ?? Infinity) - (b.dueAt ?? Infinity);
    })
    .slice(0, SHOWN);
}

/** A date, not a timestamp. Declared inline rather than as a named next-intl format because a
 * name that the locale config does not define silently degrades to a full `toString()`. */
const DATE_ONLY = { year: "numeric", month: "short", day: "numeric" } as const;

export async function WhatToDoNext({ plan }: { plan: PlanDetail }) {
  const t = await getTranslations("whatToDoNext");
  const format = await getFormatter();
  const actions = nextActions(plan.items);
  const remaining = plan.items.filter((item) => item.status !== "done").length;

  if (actions.length === 0) {
    return (
      <Card grain className="px-6 py-8 text-center">
        <p className="text-sm font-medium text-foreground">{t("allDone.title")}</p>
        <p className="mt-1.5 text-sm text-foreground-secondary">{t("allDone.description")}</p>
      </Card>
    );
  }

  return (
    <Card grain className="px-6 py-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold tracking-tight text-foreground">{t("title")}</h2>
        <span className="text-2xs text-foreground-muted">{t("remaining", { count: remaining })}</span>
      </header>

      <ol className="mt-4 space-y-2.5">
        {actions.map((item, index) => {
          const overdue = item.dueAt !== null && item.dueAt * 1000 < Date.now();
          return (
            <li
              key={item.id}
              className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 rounded-xl border border-hairline bg-surface px-4 py-3.5"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2.5">
                  <span aria-hidden className="text-sm text-foreground-muted">
                    {index + 1}
                  </span>
                  <p className="text-sm font-medium text-foreground">{item.title}</p>
                </div>
                {/* The objective, not the rationale: what this action sets out to achieve is what
                    a person needs before starting it. The reasoning is on the plan page. */}
                <p className="mt-1 ps-6 text-2xs text-foreground-secondary">{item.objective}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {isQuickWin(item) && (
                  <Badge tone="accent">
                    <Zap className="me-1 inline h-3 w-3" strokeWidth={2} aria-hidden />
                    {t("quickWin")}
                  </Badge>
                )}
                {item.dueAt !== null && (
                  <span className={`text-2xs ${overdue ? "text-danger" : "text-foreground-muted"}`}>
                    {overdue
                      ? t("overdue")
                      : t("due", { date: format.dateTime(new Date(item.dueAt * 1000), DATE_ONLY) })}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      <Link
        href="/plan"
        className="mt-4 inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
      >
        {t("cta")}
        <ArrowRight className="h-4 w-4" strokeWidth={2} />
      </Link>
    </Card>
  );
}
