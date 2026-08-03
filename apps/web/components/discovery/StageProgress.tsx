"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { DiscoveryProgress } from "@/lib/discovery/types";

/**
 * A segmented, stage-based progress indicator — deliberately NOT "question N of M" (ADR 0066):
 * the total number of questions varies session to session by design, so the interview shows
 * where you are in a fixed, small set of stages instead.
 */
export function StageProgress({ progress }: { progress: DiscoveryProgress }) {
  const t = useTranslations("discoveryInterview");
  const segments = Array.from({ length: progress.stageCount });

  return (
    <div className="space-y-2">
      <div className="flex gap-1.5">
        {segments.map((_, index) => (
          <div
            key={index}
            className={cn(
              "h-1.5 flex-1 rounded-full transition-colors duration-200",
              index <= progress.stageIndex ? "bg-accent" : "bg-surface-2",
            )}
          />
        ))}
      </div>
      <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
        {t(`stage.${progress.stage}`)}
      </p>
    </div>
  );
}
