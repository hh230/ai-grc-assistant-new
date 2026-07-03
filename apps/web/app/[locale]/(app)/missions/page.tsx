import type { Metadata } from "next";
import { Workflow } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export const metadata: Metadata = {
  title: "Missions · Sentinel GRC",
};

export default async function MissionsPage() {
  const t = await getTranslations("placeholders.missions");
  return (
    <PlaceholderPage
      eyebrow={t("eyebrow")}
      title={t("title")}
      description={t("description")}
      icon={Workflow}
    />
  );
}
