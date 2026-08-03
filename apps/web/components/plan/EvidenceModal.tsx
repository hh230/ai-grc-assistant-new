"use client";

import { useState, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import { Loader2, Plus, X } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { useAttachPlanItemEvidence } from "@/hooks/usePlanExecution";
import type { PlanItem } from "@/lib/planExecution/types";
import { cn } from "@/lib/utils";

interface EvidenceModalProps {
  item: PlanItem;
  onClose: () => void;
}

/**
 * Always optional, never a completion gate (ADR 0066 §5.4) — this modal only ever changes the
 * "Evidence-backed" vs "Reported by you" badge, never the item's status. Evidence is a free-text
 * reference (document name, ticket id, link) — deferred integration with the full Evidence
 * picker/`control_ids` system is a deliberate later enhancement (§5.4), not built here.
 */
export function EvidenceModal({ item, onClose }: EvidenceModalProps) {
  const t = useTranslations("planExecution");
  const [ids, setIds] = useState<string[]>(item.evidenceIds);
  const [draft, setDraft] = useState("");
  const attach = useAttachPlanItemEvidence();

  function addDraft() {
    const value = draft.trim();
    if (!value || ids.includes(value)) return;
    setIds((prev) => [...prev, value]);
    setDraft("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      addDraft();
    }
  }

  async function save() {
    await attach.mutateAsync({ itemId: item.id, evidenceIds: ids });
    onClose();
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t("evidenceModal.title")}
      description={t("evidenceModal.description")}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-lg border border-hairline bg-surface px-3 text-sm text-foreground-secondary hover:text-foreground"
          >
            {t("evidenceModal.cancel")}
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={attach.isPending}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow hover:opacity-90 active:scale-[0.98] disabled:opacity-60"
          >
            {attach.isPending && <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />}
            {t("evidenceModal.save")}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t("evidenceModal.placeholder")}
            className="h-9 flex-1 rounded-lg border border-hairline bg-surface px-3 text-sm text-foreground outline-none focus:border-hairline-strong"
          />
          <button
            type="button"
            onClick={addDraft}
            className="inline-flex h-9 items-center gap-1 rounded-lg border border-hairline-strong bg-surface px-3 text-sm text-foreground-secondary hover:bg-surface-elevated"
          >
            <Plus className="h-4 w-4" strokeWidth={1.75} />
            {t("evidenceModal.add")}
          </button>
        </div>
        {ids.length === 0 ? (
          <p className="text-xs text-foreground-muted">{t("evidenceModal.empty")}</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {ids.map((id) => (
              <li
                key={id}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border border-hairline bg-surface-elevated px-2.5 py-1 text-xs text-foreground-secondary",
                )}
              >
                {id}
                <button
                  type="button"
                  onClick={() => setIds((prev) => prev.filter((existing) => existing !== id))}
                  aria-label="Remove"
                  className="text-foreground-muted hover:text-danger"
                >
                  <X className="h-3 w-3" strokeWidth={2} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}
