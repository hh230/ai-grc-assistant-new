"use client";

import { useTranslations } from "next-intl";
import { TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { MaturityStars } from "@/components/governance/MaturityStars";
import { MATURITY_DIMENSION_ORDER, type MaturityRating } from "@/lib/planExecution/types";

interface MaturityJourneyProps {
  baseline: Record<string, MaturityRating>;
  current: Record<string, MaturityRating> | null;
}

/**
 * "You started at ⭐⭐☆☆☆, you're at ⭐⭐⭐☆☆ now" (ADR 0066 §5.3) — the visible payoff of
 * completing plan items: the same deterministic scale, two points in time, no new inference.
 */
export function MaturityJourney({ baseline, current }: MaturityJourneyProps) {
  const t = useTranslations("planExecution");

  return (
    <Card>
      <SectionHeader
        title={t("maturityJourney.title")}
        description={t("maturityJourney.description")}
      />
      <ul className="mt-4 space-y-3">
        {MATURITY_DIMENSION_ORDER.map((dimension) => {
          const start = baseline[dimension];
          const now = current?.[dimension];
          if (!start) return null;
          const delta = now ? now.stars - start.stars : 0;
          return (
            <li
              key={dimension}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-hairline px-3.5 py-2.5"
            >
              <div className="flex items-center gap-2 text-sm">
                <TrendingUp className="h-3.5 w-3.5 text-foreground-muted" strokeWidth={1.75} />
                <span className="font-medium text-foreground-secondary">
                  {t(`dimensions.${dimension}` as never)}
                </span>
              </div>
              <div className="flex items-center gap-2.5 text-sm">
                <span className="flex items-center gap-1 text-2xs text-foreground-muted">
                  <MaturityStars stars={start.stars} muted />
                </span>
                <span aria-hidden className="text-foreground-muted">
                  →
                </span>
                <span className="flex items-center gap-1.5">
                  <MaturityStars stars={now?.stars ?? start.stars} />
                  <span className="text-2xs font-medium text-foreground-secondary">
                    {t(`maturityLabels.${(now ?? start).label}` as never)}
                  </span>
                </span>
                {delta > 0 && (
                  <span className="rounded-full bg-success-soft px-1.5 py-0.5 text-2xs font-medium text-success">
                    +{delta}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
