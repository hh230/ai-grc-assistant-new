"use client";

import { Copy } from "lucide-react";
import { useRouter } from "@/i18n/navigation";
import { Modal } from "@/components/ui/Modal";
import { useStartAnalysis } from "@/hooks/useAnalyses";
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
  const router = useRouter();
  const start = useStartAnalysis(document?.id ?? "");

  if (!document) return null;

  return (
    <Modal
      open
      onClose={onClose}
      title="Already uploaded and analyzed"
      description={`"${document.fileName}" has the exact same content as a document already in your workspace.`}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 items-center rounded-lg border border-hairline bg-surface px-3.5 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={start.isPending}
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
            {start.isPending ? "Starting…" : "Re-run analysis anyway"}
          </button>
          <button
            type="button"
            onClick={() => {
              onClose();
              router.push(`/analysis?doc=${document.id}`);
            }}
            className="inline-flex h-9 items-center rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90"
          >
            Open previous analysis
          </button>
        </>
      }
    >
      <div className="flex items-center gap-3 rounded-lg border border-hairline bg-surface/40 px-3 py-2.5">
        <Copy className="h-4 w-4 shrink-0 text-foreground-muted" strokeWidth={1.75} />
        <p className="text-xs text-foreground-secondary">
          No new document was created — nothing was re-uploaded. You can open the existing
          analysis history, or re-run analysis if the AI engine or scoring rules have changed
          since it was last analyzed.
        </p>
      </div>
    </Modal>
  );
}
