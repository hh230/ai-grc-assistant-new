import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Workflow, FileSearch, UserCheck } from "lucide-react";
import { Hero } from "@/components/marketing/Hero";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { CTASection } from "@/components/marketing/CTASection";

export const metadata: Metadata = {
  title: "About Rasheed",
  description:
    "Rasheed brings policies, controls, risks, and evidence together into one unified workspace for governance, risk, and compliance.",
};

const CARD_ITEMS = [
  { icon: Workflow, key: "organizing" },
  { icon: FileSearch, key: "analysis" },
  { icon: UserCheck, key: "expertise" },
] as const;

export default async function AboutRasheedPage() {
  const t = await getTranslations("aboutPage");

  const cards = CARD_ITEMS.map(({ icon, key }) => ({
    icon,
    title: t(`cards.${key}.title`),
    description: t(`cards.${key}.description`),
  }));

  return (
    <>
      <Hero
        title={t("hero.title")}
        subtitle={t("hero.subtitle")}
        description={t("hero.description")}
      />

      <section className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
        <FeatureGrid items={cards} columns={3} />
      </section>

      <CTASection
        title={t("cta.title")}
        description={t("cta.description")}
        ctaLabel={t("cta.button")}
      />
    </>
  );
}
