import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Hero } from "@/components/marketing/Hero";
import { FAQAccordion } from "@/components/marketing/FAQAccordion";
import { CTASection } from "@/components/marketing/CTASection";

export const metadata: Metadata = {
  title: "FAQ · Rasheed",
  description: "Answers to common questions about Rasheed — data handling, human oversight, frameworks, and getting started.",
};

const FAQ_KEYS = ["q1", "q2", "q3", "q4", "q5", "q6"] as const;

export default async function FAQPage() {
  const t = await getTranslations("faqPage");

  const faqItems = FAQ_KEYS.map((key) => ({
    question: t(`items.${key}.question`),
    answer: t(`items.${key}.answer`),
  }));

  return (
    <>
      <Hero title={t("hero.title")} description={t("hero.description")} />

      <section className="mx-auto max-w-[760px] px-4 pb-20 sm:px-6">
        <FAQAccordion items={faqItems} />
      </section>

      <CTASection title={t("cta.title")} description={t("cta.description")} />
    </>
  );
}
