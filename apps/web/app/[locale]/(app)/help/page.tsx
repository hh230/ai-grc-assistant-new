import type { Metadata } from "next";
import { LifeBuoy } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export const metadata: Metadata = {
  title: "Help & Support · Sentinel GRC",
};

export default async function HelpPage() {
  const t = await getTranslations("placeholders.help");
  return (
    <PlaceholderPage
      eyebrow={t("eyebrow")}
      title={t("title")}
      description={t("description")}
      icon={LifeBuoy}
    />
  );
}
