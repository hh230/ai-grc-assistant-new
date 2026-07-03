import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Mail } from "lucide-react";
import { Hero } from "@/components/marketing/Hero";
import { CTASection } from "@/components/marketing/CTASection";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "Contact Us · Rasheed",
  description: "Get in touch with the Rasheed team about your governance, risk, and compliance needs.",
};

const CONTACT_EMAIL = "contact@rasheed.sa";

export default async function ContactPage() {
  const t = await getTranslations("contactPage");

  return (
    <>
      <Hero title={t("hero.title")} description={t("hero.description")} />

      <section className="mx-auto max-w-[560px] px-4 pb-20 sm:px-6">
        <Card className="flex flex-col items-center gap-3 p-8 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
            <Mail className="h-5 w-5 text-accent" strokeWidth={1.75} />
          </div>
          <p className="text-sm text-foreground-secondary">{t("emailLabel")}</p>
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="text-base font-medium text-accent-foreground hover:underline"
            dir="ltr"
          >
            {CONTACT_EMAIL}
          </a>
        </Card>
      </section>

      <CTASection title={t("cta.title")} description={t("cta.description")} />
    </>
  );
}
