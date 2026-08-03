"use client";

import { useTranslations } from "next-intl";
import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type JourneyStage = "discovery" | "report" | "plan";

const STAGES: JourneyStage[] = ["discovery", "report", "plan"];

interface JourneyStepperProps {
  current: JourneyStage;
  /** True while transitioning INTO the current stage (analyzing / activating) — shows a spinner
   * on the current node instead of its number, so the wait reads as progress, not a stall. */
  transitioning?: boolean;
}

/**
 * Discovery -> Report -> Plan, always visible during the setup journey (Product Flow
 * Simplification) — the direct answer to "does the user know where they are and where this
 * ends." Not shown on `/plan` itself: arriving there IS the end of this particular question,
 * and Plan Execution is its own ongoing destination, not a 4th step to track progress through.
 */
export function JourneyStepper({ current, transitioning = false }: JourneyStepperProps) {
  const t = useTranslations("governanceReport.stepper");
  const currentIndex = STAGES.indexOf(current);

  return (
    <ol className="flex items-center gap-2" aria-label={t("label")}>
      {STAGES.map((stage, index) => {
        const isDone = index < currentIndex;
        const isCurrent = index === currentIndex;
        return (
          <li key={stage} className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full text-2xs font-medium transition-colors duration-150",
                  isDone && "bg-success text-white",
                  isCurrent && !isDone && "bg-accent text-white",
                  !isDone && !isCurrent && "border border-hairline-strong bg-surface text-foreground-muted",
                )}
                aria-current={isCurrent ? "step" : undefined}
              >
                {isDone ? (
                  <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
                ) : isCurrent && transitioning ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2.5} />
                ) : (
                  index + 1
                )}
              </span>
              <span
                className={cn(
                  "text-xs font-medium",
                  isCurrent ? "text-foreground" : "text-foreground-muted",
                )}
              >
                {t(`stages.${stage}` as never)}
              </span>
            </div>
            {index < STAGES.length - 1 && (
              <span
                aria-hidden
                className={cn("h-px w-6", isDone ? "bg-success/50" : "bg-hairline-strong")}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
