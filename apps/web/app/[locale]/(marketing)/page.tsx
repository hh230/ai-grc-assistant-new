import type { Metadata } from "next";
import {
  ShieldCheck,
  FileSearch,
  Workflow,
  MessageSquareText,
  TriangleAlert,
  FileBarChart,
  ArrowRight,
} from "lucide-react";
import { Link } from "@/i18n/navigation";
import { Hero } from "@/components/marketing/Hero";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { FrameworkLogoStrip } from "@/components/marketing/FrameworkLogoStrip";
import { CTASection } from "@/components/marketing/CTASection";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "Sentinel GRC — Governance, Risk & Compliance, grounded and audit-ready",
  description:
    "An AI-assisted platform for Governance, Risk, Compliance, Privacy, and Legal teams — every answer grounded in your evidence, cited, and reviewed by a human before it counts.",
};

const HOME_FEATURES = [
  {
    icon: ShieldCheck,
    title: "Control mapping across frameworks",
    description:
      "Map evidence and controls once, and see coverage across every framework you're held to — no duplicate work per regulator.",
  },
  {
    icon: FileSearch,
    title: "Grounded, cited answers",
    description:
      "Every compliance claim traces back to your own documents and the framework text — no uncited guesses on matters that matter.",
  },
  {
    icon: Workflow,
    title: "Governed missions, not chat",
    description:
      "Gap analyses, evidence collection, and reporting run as trackable missions with a full audit trail, not a scrolling transcript.",
  },
  {
    icon: TriangleAlert,
    title: "Risk register with real workflow",
    description:
      "Score, mitigate, and accept risk with human sign-off gates — risk acceptance always requires a qualified person's approval.",
  },
  {
    icon: MessageSquareText,
    title: "Ask your compliance posture",
    description:
      "Ask plain-language questions and get answers grounded in your evidence, with sources you can open and verify.",
  },
  {
    icon: FileBarChart,
    title: "Audit-ready reporting",
    description:
      "Generate executive, compliance, and risk reports on demand, exportable for auditors and leadership alike.",
  },
];

export default function MarketingHomePage() {
  return (
    <>
      <Hero
        eyebrow="Governance · Risk · Compliance"
        title="Compliance work your auditors will trust"
        description="Sentinel GRC helps Governance, Risk, Compliance, Privacy, and Legal teams author, map, and monitor controls across every framework you answer to — grounded in your own evidence, reviewed by your people."
        primaryCta={{ label: "Get started", href: "/login" }}
        secondaryCta={{ label: "See how it works", href: "/how-it-works" }}
      >
        <div className="mt-14">
          <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
            Built for the frameworks you&apos;re already held to
          </p>
          <FrameworkLogoStrip className="mt-4" />
        </div>
      </Hero>

      <section className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-[620px] text-center">
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Everything a compliance team needs, grounded in evidence
          </h2>
          <p className="text-balance mt-3 text-sm leading-relaxed text-foreground-secondary sm:text-base">
            Controls, policies, risk, and reporting — connected to the documents that prove
            them, not disconnected spreadsheets.
          </p>
        </div>
        <FeatureGrid items={HOME_FEATURES} className="mt-12" />
      </section>

      <section className="border-t border-hairline bg-canvas">
        <div className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
          <Card className="flex flex-col items-center gap-6 p-10 text-center sm:p-14 lg:flex-row lg:justify-between lg:text-start">
            <div>
              <h2 className="text-xl font-semibold tracking-tight text-foreground">
                A human always decides
              </h2>
              <p className="mt-2 max-w-[520px] text-sm leading-relaxed text-foreground-secondary">
                The platform proposes, drafts, and analyzes — a qualified person on your team
                approves anything consequential, like a control sign-off or a risk acceptance.
              </p>
            </div>
            <Link
              href="/product"
              className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-lg border border-hairline bg-surface px-4 text-sm font-medium text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
            >
              Read the product overview
              <ArrowRight className="h-4 w-4 flip-rtl" strokeWidth={1.75} />
            </Link>
          </Card>
        </div>
      </section>

      <CTASection
        title="See your compliance posture clearly"
        description="Start with your existing policies and evidence — Sentinel GRC grounds every answer in what you already have."
      />
    </>
  );
}
