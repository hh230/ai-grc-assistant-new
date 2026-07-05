import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { requireSession } from "@/lib/auth/server";
import { PolicyIntelligenceWorkspace } from "@/components/policyIntelligence/PolicyIntelligenceWorkspace";

export const metadata: Metadata = {
  title: "Policy Intelligence · Rasheed",
};

export default async function PolicyIntelligencePage() {
  await requireSession();
  const t = await getTranslations("policyIntelligencePage");

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

      <PolicyIntelligenceWorkspace />
    </div>
  );
}
