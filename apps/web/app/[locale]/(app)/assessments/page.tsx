import type { Metadata } from "next";
import { pageTitle } from "@/lib/pageMetadata";
import { ClipboardList } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export async function generateMetadata(): Promise<Metadata> {
  return pageTitle("placeholders.assessments.title");
}

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
