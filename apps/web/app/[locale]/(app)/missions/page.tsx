import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { requireSession } from "@/lib/auth/server";
import { MissionsList } from "@/components/missions/MissionsList";
import { pageTitle } from "@/lib/pageMetadata";

export async function generateMetadata(): Promise<Metadata> {
  return pageTitle("missionsPage.title");
}

export default async function MissionsPage() {
  await requireSession();
  const t = await getTranslations("missionsPage");

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

      <MissionsList />
    </div>
  );
}
