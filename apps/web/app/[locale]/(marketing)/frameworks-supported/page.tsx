import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Library } from "lucide-react";
import { Hero } from "@/components/marketing/Hero";
import { CTASection } from "@/components/marketing/CTASection";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SUPPORTED_FRAMEWORKS } from "@/components/marketing/FrameworkLogoStrip";

export const metadata: Metadata = {
  title: "Frameworks Supported · Sentinel GRC",
  description:
    "Regional and international compliance frameworks Sentinel GRC maps controls and evidence against, including NCA ECC, SAMA, PDPL, ISO 27001, and NIST CSF.",
};

export default async function FrameworksSupportedPage() {
  const t = await getTranslations("frameworksSupportedPage");
  const tFrameworks = await getTranslations("marketingFrameworks");

  return (
    <>
      <Hero
        eyebrow={t("hero.eyebrow")}
        title={t("hero.title")}
        description={t("hero.description")}
      />

      <section className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {SUPPORTED_FRAMEWORKS.map((fw) => (
            <Card key={fw.shortName} className="p-7">
              <div className="flex items-start justify-between gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
                  <Library className="h-[18px] w-[18px] text-accent" strokeWidth={1.75} />
                </div>
                <Badge tone={fw.regionKey === "ksa" ? "accent" : "neutral"}>
                  {tFrameworks(`${fw.key}.region`)}
                </Badge>
              </div>
              <h3 className="mt-5 text-base font-semibold tracking-tight text-foreground">
                {fw.shortName}
              </h3>
              <p className="mt-1 text-xs text-foreground-muted">{tFrameworks(`${fw.key}.name`)}</p>
              <p className="mt-3 text-sm leading-relaxed text-foreground-secondary">
                {tFrameworks(`${fw.key}.description`)}
              </p>
            </Card>
          ))}
        </div>

        <p className="mx-auto mt-10 max-w-[560px] text-center text-sm text-foreground-muted">
          {t("footerNote")}
        </p>
      </section>

      <CTASection title={t("cta.title")} description={t("cta.description")} />
    </>
  );
}
