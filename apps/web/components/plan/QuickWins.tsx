"use client";

import { useTranslations } from "next-intl";
import { Loader2, Zap } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { useStartPlanItem } from "@/hooks/usePlanExecution";
import { isQuickWin } from "@/lib/planExecution/grouping";
import type { PlanItem } from "@/lib/planExecution/types";

/** Small effort, high/critical urgency, not yet done (ADR 0066 §4) — no new logic, a
 * rendering-time filter so the client sees what they can start immediately, ahead of the full
 * plan. Mirrors the report's "Quick Wins" section, now as a live, actionable strip. */
export function QuickWins({ items }: { items: PlanItem[] }) {
  const t = useTranslations("planExecution");
  const start = useStartPlanItem();
  const wins = items.filter(isQuickWin);

  if (wins.length === 0) return null;

  return (
    <Card grain>
      <SectionHeader
        title={t("quickWins.title")}
        description={t("quickWins.description")}
        action={
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-soft">
            <Zap className="h-3.5 w-3.5 text-accent-foreground" strokeWidth={1.75} />
          </span>
        }
      />
      <ul className="mt-3.5 space-y-2">
        {wins.map((item) => (
          <li
            key={item.id}
            className="flex items-center justify-between gap-3 rounded-lg border border-hairline bg-surface px-3 py-2 text-sm"
          >
            <span className="min-w-0 truncate text-foreground-secondary">{item.title}</span>
            <button
              type="button"
              disabled={start.isPending}
              onClick={() => start.mutate(item.id)}
              className="inline-flex h-7 shrink-0 items-center gap-1 rounded-lg bg-accent px-2.5 text-2xs font-medium text-white shadow-glow hover:opacity-90 disabled:opacity-60"
            >
              {start.isPending && start.variables === item.id && (
                <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
              )}
              {t("item.start")}
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
