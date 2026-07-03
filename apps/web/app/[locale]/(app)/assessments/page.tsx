import type { Metadata } from "next";
import { ClipboardList } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export const metadata: Metadata = {
  title: "Assessments · Sentinel GRC",
};

export default async function AssessmentsPage() {
  const t = await getTranslations("placeholders.assessments");
  return (
    <PlaceholderPage
      eyebrow={t("eyebrow")}
      title={t("title")}
      description={t("description")}
      icon={ClipboardList}
    />
  );
}
