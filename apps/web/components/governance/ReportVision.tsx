"use client";

import { useTranslations } from "next-intl";
import { Sparkles } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { MaturityStars } from "./MaturityStars";
import { MATURITY_DIMENSION_ORDER, type MaturityRating } from "@/lib/planExecution/types";

/**
 * Section 10 (ADR 0066 §4): "if this plan is fully executed" — a second, hypothetical run of the
 * exact same deterministic maturity-scoring pass, never a new inference. Same rendering as the
 * live Plan's Maturity Journey (baseline -> current); here it's baseline -> the best case this
 * plan makes possible, projecting forward instead of looking back.
 */
export function GovernanceVisionSection({
  baseline,
  vision,
}: {
  baseline: Record<string, MaturityRating>;
  vision: Record<string, MaturityRating>;
}) {
  const t = useTranslations("governanceReport");

  return (
    <Card grain>
      <SectionHeader
        title={t("governanceVision.title")}
        description={t("governanceVision.description")}
        action={
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-soft">
            <Sparkles className="h-3.5 w-3.5 text-accent-foreground" strokeWidth={1.75} />
          </span>
        }
      />
      <ul className="mt-3.5 space-y-2.5">
        {MATURITY_DIMENSION_ORDER.map((dimension) => {
          const start = baseline[dimension];
          const target = vision[dimension];
          if (!start || !target) return null;
          return (
            <li key={dimension} className="flex items-center justify-between gap-3 text-sm">
              <span className="text-foreground-secondary">{t(`dimensions.${dimension}` as never)}</span>
              <span className="flex items-center gap-2.5">
                <MaturityStars stars={start.stars} muted />
                <span aria-hidden className="text-foreground-muted">
                  →
                </span>
                <MaturityStars stars={target.stars} />
                <span className="text-2xs font-medium text-foreground-secondary">
                  {t(`maturityLabels.${target.label}` as never)}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
