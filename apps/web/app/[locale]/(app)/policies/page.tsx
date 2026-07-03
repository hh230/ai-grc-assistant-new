import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { can } from "@/lib/auth/permissions";
import { requireSession } from "@/lib/auth/server";
import { PoliciesWorkspace } from "@/components/policies/PoliciesWorkspace";

export const metadata: Metadata = {
  title: "Policies · Rasheed",
};

export default async function PoliciesPage() {
  const session = await requireSession();
  const t = await getTranslations("policiesPage");
  const permissions = {
    canCreate: can(session.roles, "create", "policy"),
    canUpdate: can(session.roles, "update", "policy"),
    canPublish: can(session.roles, "publish", "policy"),
    canDelete: can(session.roles, "delete", "policy"),
  };

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

      <PoliciesWorkspace {...permissions} />
    </div>
  );
}
