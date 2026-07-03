import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Workflow, FileSearch, UserCheck } from "lucide-react";
import { Hero } from "@/components/marketing/Hero";
import { CTASection } from "@/components/marketing/CTASection";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "Product Overview · Rasheed",
  description:
    "How Rasheed organizes compliance work into governed missions, grounds every answer in evidence, and keeps a human in charge of consequential decisions.",
};

const SECTION_ITEMS = [
  { icon: Workflow, key: "missions" },
  { icon: FileSearch, key: "grounded" },
  { icon: UserCheck, key: "human" },
] as const;

export default async function ProductOverviewPage() {
  const t = await getTranslations("productPage");

  const sections = SECTION_ITEMS.map(({ icon, key }) => ({
    icon,
    title: t(`sections.${key}.title`),
    description: t(`sections.${key}.description`),
  }));

  return (
    <>
      <Hero title={t("hero.title")} description={t("hero.description")} />

      <section className="mx-auto max-w-[900px] space-y-16 px-4 py-20 sm:px-6">
        {sections.map((section, index) => {
          const Icon = section.icon;
          return (
            <div
              key={section.title}
              className="grid grid-cols-1 items-center gap-8 lg:grid-cols-12"
            >
              <div
                className={
                  index % 2 === 1 ? "lg:order-2 lg:col-span-5" : "lg:col-span-5"
                }
              >
                <Card grain className="flex aspect-[4/3] items-center justify-center p-10">
                  <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-hairline-strong bg-surface-2 shadow-soft">
                    <Icon className="h-9 w-9 text-accent" strokeWidth={1.5} />
                  </div>
                </Card>
              </div>
              <div className={index % 2 === 1 ? "lg:order-1 lg:col-span-7" : "lg:col-span-7"}>
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                  {section.title}
                </h2>
                <p className="mt-4 text-base leading-relaxed text-foreground-secondary">
                  {section.description}
                </p>
              </div>
            </div>
          );
        })}
      </section>

      <CTASection title={t("cta.title")} description={t("cta.description")} />
    </>
  );
}
