"use client";

import { useTranslations } from "next-intl";
import { Check, Loader2, FileText, Sparkles } from "lucide-react";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

interface AnalysisProgressProps {
  steps: readonly string[];
  /** Number of completed steps; the step at this index is the active one. */
  completed: number;
  fileName: string;
  fileSize: string;
  done: boolean;
}

export function AnalysisProgress({
  steps,
  completed,
  fileName,
  fileSize,
  done,
}: AnalysisProgressProps) {
  const t = useTranslations("analysisProgress");
  const progress = Math.round((completed / steps.length) * 100);

  return (
    <div className="animate-fade-in-up rounded-3xl border border-hairline bg-surface p-6 shadow-soft sm:p-8">
      {/* Document header */}
      <div className="flex items-center gap-3.5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-hairline bg-surface-2">
          <FileText className="h-5 w-5 text-foreground-secondary" strokeWidth={1.5} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{fileName}</p>
          <p className="mt-0.5 text-2xs text-foreground-muted">
            {t("fileSizeSuffix", { size: fileSize })}
          </p>
        </div>
        <Badge tone="accent" dot>
          {done ? t("complete") : t("analyzing")}
        </Badge>
      </div>

      {/* Overall progress */}
      <div className="mt-6">
        <div className="flex items-center justify-between text-2xs text-foreground-muted">
          <span className="flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-accent-foreground" strokeWidth={1.75} />
            {t("analysisInProgress")}
          </span>
          <span className="font-mono tabular-nums">{progress}%</span>
        </div>
        <ProgressBar value={progress} tone="accent" className="mt-2 h-2" />
      </div>

      {/* Step list */}
      <ol className="mt-6 space-y-1">
        {steps.map((step, index) => {
          const state = index < completed ? "done" : index === completed ? "active" : "pending";
          return (
            <li
              key={step}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors duration-200",
                state === "active" && "bg-white/[0.03]",
              )}
            >
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition-colors duration-200",
                  state === "done" && "border-success/30 bg-success-soft text-success",
                  state === "active" && "border-accent/30 bg-accent-soft text-accent-foreground",
                  state === "pending" && "border-hairline text-foreground-muted",
                )}
              >
                {state === "done" ? (
                  <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
                ) : state === "active" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />
                )}
              </span>
              <span
                className={cn(
                  "flex-1 text-sm transition-colors duration-200",
                  state === "pending" ? "text-foreground-muted" : "text-foreground",
                )}
              >
                {step}
              </span>
              <span className="text-2xs text-foreground-muted">
                {state === "done" ? t("done") : state === "active" ? t("running") : t("queued")}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="mt-5 text-center text-2xs text-foreground-muted">
        {done ? t("openingReport") : t("staySeconds")}
      </p>
    </div>
  );
}
