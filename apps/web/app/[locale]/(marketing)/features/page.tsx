import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import {
  ShieldCheck,
  FileText,
  Library,
  TriangleAlert,
  FolderArchive,
  FileBarChart,
  MessageSquareText,
  ClipboardList,
} from "lucide-react";
import { Hero } from "@/components/marketing/Hero";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { CTASection } from "@/components/marketing/CTASection";

export const metadata: Metadata = {
  title: "Features · Rasheed",
  description: "Every feature of the Rasheed governance, risk, and compliance workspace.",
};

const FEATURE_ITEMS = [
  { icon: ShieldCheck, key: "controls" },
  { icon: FileText, key: "policies" },
  { icon: Library, key: "frameworks" },
  { icon: TriangleAlert, key: "riskRegister" },
  { icon: FolderArchive, key: "evidence" },
  { icon: MessageSquareText, key: "aiWorkspace" },
  { icon: ClipboardList, key: "assessments" },
  { icon: FileBarChart, key: "reports" },
] as const;

export default async function FeaturesPage() {
  const t = await getTranslations("featuresPage");

  const features = FEATURE_ITEMS.map(({ icon, key }) => ({
    icon,
    title: t(`items.${key}.title`),
    description: t(`items.${key}.description`),
  }));

  return (
    <>
      <Hero title={t("hero.title")} description={t("hero.description")} />

      <section className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
        <FeatureGrid items={features} />
      </section>

      <CTASection title={t("cta.title")} description={t("cta.description")} />
    </>
  );
}
