import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { requireRoles } from "@/lib/auth/server";
import { AccessRequestsWorkspace } from "@/components/accessRequests/AccessRequestsWorkspace";

export const metadata: Metadata = {
  title: "Access Requests · Rasheed",
};

// Admin-only (CLAUDE.md §20, server-enforced RBAC — matches the Regulation Review page's own
// guard; app/api/access-requests's own `_adminGuard.ts` re-checks this independently).
export default async function AccessRequestsPage() {
  await requireRoles("owner", "admin");
  const t = await getTranslations("accessRequestsPage");

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">{t("description")}</p>
      </header>

      <AccessRequestsWorkspace />
    </div>
  );
}
