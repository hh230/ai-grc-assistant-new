"use client";

import { Copy } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Modal } from "@/components/ui/Modal";
import { useAnalysisUsage, useStartAnalysis } from "@/hooks/useAnalyses";
import type { DocumentDto } from "@/lib/documents/types";

interface DuplicateDocumentDialogProps {
  document: DocumentDto | null;
  onClose: () => void;
}

/**
 * V2-P2.5 upload-time dedupe: shown when a file's content hash matches a document already in
 * the tenant. Offers to open the existing analysis history, or force a re-run (e.g. because
 * scoring rules or the AI engine changed since the last run).
 */
export function DuplicateDocumentDialog({ document, onClose }: DuplicateDocumentDialogProps) {
  const t = useTranslations("duplicateDocumentDialog");
  const tAnalysis = useTranslations("analysisDetail");
  const router = useRouter();
  const start = useStartAnalysis(document?.id ?? "");
  const { data: usage } = useAnalysisUsage();
  const atLimit = usage ? usage.remaining <= 0 : false;

  if (!document) return null;

  return (
    <Modal
      open
      onClose={onClose}
      title={t("title")}
      description={t("description", { fileName: document.fileName })}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 items-center rounded-lg border border-hairline bg-surface px-3.5 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            disabled={start.isPending || atLimit}
            onClick={() => {
              start.mutate(undefined, {
                onSuccess: () => {
                  onClose();
                  router.push(`/analysis?doc=${document.id}`);
                },
              });
            }}
            className="inline-flex h-9 items-center rounded-lg border border-hairline bg-surface px-3.5 text-sm font-medium text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground disabled:opacity-60"
          >
            {start.isPending ? t("starting") : t("rerunAnyway")}
          </button>
          <button
            type="button"
            onClick={() => {
              onClose();
              router.push(`/analysis?doc=${document.id}`);
            }}
            className="inline-flex h-9 items-center rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
          >
            {t("openPrevious")}
          </button>
        </>
      }
    >
      <div className="flex items-center gap-3 rounded-lg border border-hairline bg-surface/40 px-3 py-2.5">
        <Copy className="h-4 w-4 shrink-0 text-foreground-muted" strokeWidth={1.75} />
        <p className="text-xs text-foreground-secondary">{t("bodyText")}</p>
      </div>
      {atLimit && usage && (
        <p className="mt-3 rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-2xs text-warning">
          {tAnalysis("limitReached", { limit: usage.limit })}
        </p>
      )}
    </Modal>
  );
}
