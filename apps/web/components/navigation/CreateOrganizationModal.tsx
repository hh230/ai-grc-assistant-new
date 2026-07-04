"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { Loader2, TriangleAlert } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Modal } from "@/components/ui/Modal";
import { createOrganization } from "@/lib/organizations/client";

interface CreateOrganizationModalProps {
  open: boolean;
  onClose: () => void;
  /** Runs after the new organization is created and the session has switched into it. */
  onCreated: () => void;
}

const inputClass =
  "w-full rounded-lg border border-hairline bg-surface/60 px-3 h-9 text-sm text-foreground outline-none focus:border-hairline-strong";

function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">{children}</span>
  );
}

export function CreateOrganizationModal({
  open,
  onClose,
  onCreated,
}: CreateOrganizationModalProps) {
  const t = useTranslations("orgSwitcher.createModal");
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [orgType, setOrgType] = useState("");
  const [industry, setIndustry] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const reset = () => {
    setName("");
    setOrgType("");
    setIndustry("");
    setError(null);
  };

  const handleClose = () => {
    if (isSaving) return;
    reset();
    onClose();
  };

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !orgType.trim() || !industry.trim()) {
      setError(t("requiredError"));
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await createOrganization({ name: name.trim(), orgType: orgType.trim(), industry: industry.trim() });
      await queryClient.invalidateQueries({ queryKey: ["organizations"] });
      reset();
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("genericError"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={t("title")}
      description={t("description")}
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            disabled={isSaving}
            className="h-9 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary hover:text-foreground disabled:opacity-60"
          >
            {t("cancel")}
          </button>
          <button
            type="submit"
            form="create-organization-form"
            disabled={isSaving}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow hover:opacity-90 active:scale-[0.98] disabled:opacity-60"
          >
            {isSaving && <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />}
            {t("save")}
          </button>
        </>
      }
    >
      <form id="create-organization-form" onSubmit={onSubmit} className="space-y-4">
        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.75} />
            <span>{error}</span>
          </div>
        )}
        <label className="block">
          <FieldLabel>{t("form.name")}</FieldLabel>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputClass}
            placeholder={t("form.namePlaceholder")}
            autoFocus
          />
        </label>
        <label className="block">
          <FieldLabel>{t("form.orgType")}</FieldLabel>
          <input
            value={orgType}
            onChange={(e) => setOrgType(e.target.value)}
            className={inputClass}
            placeholder={t("form.orgTypePlaceholder")}
          />
        </label>
        <label className="block">
          <FieldLabel>{t("form.industry")}</FieldLabel>
          <input
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className={inputClass}
            placeholder={t("form.industryPlaceholder")}
          />
        </label>
      </form>
    </Modal>
  );
}
