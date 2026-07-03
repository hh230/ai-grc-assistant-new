import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { can } from "@/lib/auth/permissions";
import { requireSession } from "@/lib/auth/server";
import { EvidenceWorkspace } from "@/components/evidence/EvidenceWorkspace";

export const metadata: Metadata = {
  title: "Evidence · Rasheed",
};

export default async function EvidencePage() {
  const session = await requireSession();
  const t = await getTranslations("evidencePage");
  const canCreate = can(session.roles, "create", "evidence");
  const canUpdate = can(session.roles, "update", "evidence");
  const canDelete = can(session.roles, "delete", "evidence");

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          {t("title")}
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">{t("description")}</p>
      </header>

      <EvidenceWorkspace canCreate={canCreate} canUpdate={canUpdate} canDelete={canDelete} />
    </div>
  );
}
