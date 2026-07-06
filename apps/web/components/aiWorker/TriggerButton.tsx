"use client";

import { useTranslations } from "next-intl";
import { Loader2, Zap } from "lucide-react";
import { useTriggerWorkerRun, useWorkerStatus } from "@/hooks/useKnowledgeWorker";

export function TriggerButton() {
  const t = useTranslations("aiWorkerWorkspace.trigger");
  const { data: status } = useWorkerStatus();
  const mutation = useTriggerWorkerRun();

  const alreadyPending = status?.manualTriggerRequested ?? false;

  return (
    <button
      type="button"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending || alreadyPending}
      className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {mutation.isPending ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Zap className="h-4 w-4" strokeWidth={1.75} />
      )}
      {alreadyPending ? t("pending") : t("label")}
    </button>
  );
}
