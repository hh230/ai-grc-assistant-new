import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { requireRoles } from "@/lib/auth/server";
import { RegulationReviewWorkspace } from "@/components/regulationReview/RegulationReviewWorkspace";

export const metadata: Metadata = {
  title: "Regulation Review · Rasheed",
};

// Admin-only (CLAUDE.md §20, server-enforced RBAC — matches the AI Worker Control Center's
// own guard, and the apps/api /regulation-review router's own RBAC gate re-checks this
// independently).
export default async function RegulationReviewPage() {
  await requireRoles("owner", "admin");
  const t = await getTranslations("regulationReviewPage");

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">{t("description")}</p>
      </header>

      <RegulationReviewWorkspace />
    </div>
  );
}
