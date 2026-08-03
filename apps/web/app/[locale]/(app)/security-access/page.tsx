import type { Metadata } from "next";
import { pageTitle } from "@/lib/pageMetadata";
import { getTranslations } from "next-intl/server";
import { requireSession } from "@/lib/auth/server";
import { SecurityAccessForm } from "@/components/account/SecurityAccessForm";

export async function generateMetadata(): Promise<Metadata> {
  return pageTitle("securityAccessPage.title");
}

export default async function SecurityAccessPage() {
  await requireSession();
  const t = await getTranslations("securityAccessPage");

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

      <div className="max-w-lg">
        <SecurityAccessForm />
      </div>
    </div>
  );
}
