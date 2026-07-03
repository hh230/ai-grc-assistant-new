import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import {
  ShieldCheck,
  FileSearch,
  Workflow,
  MessageSquareText,
  TriangleAlert,
  FileBarChart,
  ArrowRight,
  Upload,
  Search,
  FileBarChart2,
} from "lucide-react";
import { Link } from "@/i18n/navigation";
import { Hero } from "@/components/marketing/Hero";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { FrameworkLogoStrip, SUPPORTED_FRAMEWORKS } from "@/components/marketing/FrameworkLogoStrip";
import { TrustedByStrip } from "@/components/marketing/TrustedByStrip";
import { ProductScreenshot } from "@/components/marketing/ProductScreenshot";
import { FAQAccordion } from "@/components/marketing/FAQAccordion";
import { CTASection } from "@/components/marketing/CTASection";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "Rasheed — Governance, Risk & Compliance, grounded and audit-ready",
  description:
    "An AI-assisted platform for Governance, Risk, Compliance, Privacy, and Legal teams — every answer grounded in your evidence, cited, and reviewed by a human before it counts.",
};

const FEATURE_ITEMS = [
  { icon: ShieldCheck, key: "controlMapping" },
  { icon: FileSearch, key: "groundedAnswers" },
  { icon: Workflow, key: "governedMissions" },
  { icon: TriangleAlert, key: "riskRegister" },
  { icon: MessageSquareText, key: "askPosture" },
  { icon: FileBarChart, key: "auditReporting" },
] as const;

const STEP_ITEMS = [
  { icon: Upload, key: "step1" },
  { icon: Search, key: "step2" },
  { icon: ShieldCheck, key: "step3" },
  { icon: FileBarChart2, key: "step4" },
] as const;

const FAQ_KEYS = ["q1", "q2", "q3", "q4", "q5", "q6"] as const;

export default async function MarketingHomePage() {
  const t = await getTranslations("home");
  const tFrameworks = await getTranslations("marketingFrameworks");
  const locale = await getLocale();

  const features = FEATURE_ITEMS.map(({ icon, key }) => ({
    icon,
    title: t(`features.${key}.title`),
    description: t(`features.${key}.description`),
  }));

  const steps = STEP_ITEMS.map(({ icon, key }, i) => ({
    icon,
    step: String(i + 1),
    title: t(`howItWorks.${key}.title`),
    description: t(`howItWorks.${key}.description`),
  }));

  const faqItems = FAQ_KEYS.map((key) => ({
    question: t(`faq.${key}.question`),
    answer: t(`faq.${key}.answer`),
  }));

  return (
    <>
      <Hero
        eyebrow={t("hero.eyebrow")}
        title={t("hero.title")}
        description={t("hero.description")}
        primaryCta={{ label: t("hero.primaryCta"), href: "/login" }}
        secondaryCta={{ label: t("hero.secondaryCta"), href: "/how-it-works" }}
      />

      <section className="mx-auto max-w-[1200px] px-4 pb-16 pt-2 sm:px-6">
        <TrustedByStrip label={t("trustedBy.label")} />
      </section>

      <section className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-[680px] text-center">
          <span className="inline-flex items-center rounded-full border border-gold/30 bg-gold-soft px-3 py-1 text-2xs font-medium text-accent">
            {t("why.badge")}
          </span>
          <h2 className="text-balance mt-4 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            {t("why.title")}
          </h2>
          <p className="text-balance mt-3 text-sm leading-relaxed text-foreground-secondary sm:text-base">
            {t("why.description")}
          </p>
        </div>
        <FeatureGrid items={features} className="mt-12" />
      </section>

      <section className="border-t border-hairline bg-canvas">
        <div className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-[620px] text-center">
            <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              {t("screenshots.title")}
            </h2>
            <p className="text-balance mt-3 text-sm leading-relaxed text-foreground-secondary sm:text-base">
              {t("screenshots.description")}
            </p>
          </div>
          <div className="mt-12 grid grid-cols-1 gap-10 lg:grid-cols-2">
            <ProductScreenshot
              src={`/marketing/dashboard-${locale}.png`}
              alt="Rasheed executive dashboard showing compliance and risk scores, active frameworks, and an AI-generated executive summary"
              caption={t("screenshots.dashboardCaption")}
              width={1440}
              height={760}
            />
            <ProductScreenshot
              src={`/marketing/analysis-${locale}.png`}
              alt="Rasheed document analysis showing compliance and risk scores, findings by severity, and an AI-generated executive summary with citations"
              caption={t("screenshots.analysisCaption")}
              width={1440}
              height={900}
            />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[900px] px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-[620px] text-center">
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            {t("howItWorks.title")}
          </h2>
        </div>
        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {steps.map((item) => {
            const Icon = item.icon;
            return (
              <Card key={item.step} className="flex items-start gap-4 p-6">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 text-sm font-semibold text-accent shadow-soft">
                  {item.step}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-accent" strokeWidth={1.75} />
                    <h3 className="text-sm font-semibold tracking-tight text-foreground">
                      {item.title}
                    </h3>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-foreground-secondary">
                    {item.description}
                  </p>
                </div>
              </Card>
            );
          })}
        </div>
        <div className="mt-8 text-center">
          <Link
            href="/how-it-works"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-foreground hover:underline"
          >
            {t("howItWorks.cta")}
            <ArrowRight className="h-4 w-4 flip-rtl" strokeWidth={1.75} />
          </Link>
        </div>
      </section>

      <section className="border-t border-hairline bg-canvas">
        <div className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-[620px] text-center">
            <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              {t("frameworks.title")}
            </h2>
            <p className="text-balance mt-3 text-sm leading-relaxed text-foreground-secondary sm:text-base">
              {t("frameworks.description")}
            </p>
          </div>
          <div className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {SUPPORTED_FRAMEWORKS.map((fw) => (
              <div
                key={fw.shortName}
                className="rounded-xl border border-hairline bg-surface px-4 py-3.5 text-center shadow-soft"
              >
                <p className="text-sm font-semibold text-foreground">{fw.shortName}</p>
                <p className="mt-0.5 truncate text-2xs text-foreground-muted">
                  {tFrameworks(`${fw.key}.name`)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
        <Card className="flex flex-col items-center gap-6 p-10 text-center sm:p-14 lg:flex-row lg:justify-between lg:text-start">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-foreground">
              {t("humanDecides.title")}
            </h2>
            <p className="mt-2 max-w-[520px] text-sm leading-relaxed text-foreground-secondary">
              {t("humanDecides.description")}
            </p>
          </div>
          <Link
            href="/product"
            className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-lg border border-hairline bg-surface px-4 text-sm font-medium text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
          >
            {t("humanDecides.cta")}
            <ArrowRight className="h-4 w-4 flip-rtl" strokeWidth={1.75} />
          </Link>
        </Card>
      </section>

      <section className="border-t border-hairline bg-canvas">
        <div className="mx-auto max-w-[760px] px-4 py-20 sm:px-6">
          <div className="text-center">
            <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              {t("faq.title")}
            </h2>
          </div>
          <FAQAccordion items={faqItems} />
          <div className="mt-6 text-center">
            <Link
              href="/faq"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-foreground hover:underline"
            >
              {t("faq.cta")}
              <ArrowRight className="h-4 w-4 flip-rtl" strokeWidth={1.75} />
            </Link>
          </div>
        </div>
      </section>

      <CTASection title={t("cta.title")} description={t("cta.description")} />
    </>
  );
}
