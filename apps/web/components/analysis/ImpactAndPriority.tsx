"use client";

import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { OverallPriority, Priority } from "@/lib/analysis/types";

const PRIORITY_TONE: Record<Priority, "danger" | "warning" | "accent"> = {
  high: "danger",
  medium: "warning",
  low: "accent",
};

export function ImpactAndPriority({
  businessImpact,
  priority,
}: {
  businessImpact?: string;
  priority?: OverallPriority;
}) {
  const t = useTranslations("impactAndPriority");
  if (!businessImpact && !priority) return null;

  return (
    <Card>
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        {businessImpact && (
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">
              {t("businessImpactTitle")}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-foreground-secondary">
              {businessImpact}
            </p>
          </div>
        )}
        {priority && (
          <div className={businessImpact ? "sm:border-s sm:border-hairline sm:ps-5" : undefined}>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold tracking-tight text-foreground">
                {t("priorityTitle")}
              </h2>
              <Badge tone={PRIORITY_TONE[priority.level]}>{t(`priority.${priority.level}`)}</Badge>
            </div>
            {priority.rationale && (
              <p className="mt-2 text-sm leading-relaxed text-foreground-secondary">
                {priority.rationale}
              </p>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
