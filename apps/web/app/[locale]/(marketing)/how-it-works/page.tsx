import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Upload, Search, ShieldCheck, FileBarChart } from "lucide-react";
import { Hero } from "@/components/marketing/Hero";
import { CTASection } from "@/components/marketing/CTASection";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "How It Works · Rasheed",
  description:
    "How Rasheed turns your policies and evidence into grounded coverage, risk, and reporting.",
};

const STEP_ITEMS = [
  { icon: Upload, key: "step1" },
  { icon: Search, key: "step2" },
  { icon: ShieldCheck, key: "step3" },
  { icon: FileBarChart, key: "step4" },
] as const;

export default async function HowItWorksPage() {
  const t = await getTranslations("howItWorksPage");

  const steps = STEP_ITEMS.map(({ icon, key }, i) => ({
    icon,
    step: String(i + 1),
    title: t(`steps.${key}.title`),
    description: t(`steps.${key}.description`),
  }));

  return (
    <>
      <Hero title={t("hero.title")} description={t("hero.description")} />

      <section className="mx-auto max-w-[900px] px-4 py-20 sm:px-6">
        <div className="space-y-4">
          {steps.map((item) => {
            const Icon = item.icon;
            return (
              <Card key={item.step} className="flex items-start gap-5 p-7">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 text-sm font-semibold text-accent shadow-soft">
                  {item.step}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-accent" strokeWidth={1.75} />
                    <h3 className="text-base font-semibold tracking-tight text-foreground">
                      {item.title}
                    </h3>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-foreground-secondary">
                    {item.description}
                  </p>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      <CTASection title={t("cta.title")} description={t("cta.description")} />
    </>
  );
}
