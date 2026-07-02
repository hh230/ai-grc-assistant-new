import type { Metadata } from "next";
import { Upload, Search, ShieldCheck, FileBarChart } from "lucide-react";
import { Hero } from "@/components/marketing/Hero";
import { CTASection } from "@/components/marketing/CTASection";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "How It Works · Sentinel GRC",
  description:
    "How Sentinel GRC turns your policies and evidence into grounded coverage, risk, and reporting.",
};

const STEPS = [
  {
    icon: Upload,
    step: "1",
    title: "Bring your policies and evidence",
    description:
      "Upload the documents you already have — policies, prior audit reports, contracts, and evidence artifacts. Nothing needs to be reformatted first.",
  },
  {
    icon: Search,
    step: "2",
    title: "The platform reads and grounds them",
    description:
      "Your documents are parsed and indexed against the frameworks you select, so answers and coverage numbers are grounded in what you actually have — not a generic template.",
  },
  {
    icon: ShieldCheck,
    step: "3",
    title: "Review coverage, gaps, and risk",
    description:
      "See exactly which controls are covered, which are gaps, and how your risk register looks — with every number traceable back to a source document.",
  },
  {
    icon: FileBarChart,
    step: "4",
    title: "Act, approve, and report",
    description:
      "Draft policies, close gaps, and accept risk with a clear sign-off trail, then generate an audit-ready report whenever you need one.",
  },
] as const;

export default function HowItWorksPage() {
  return (
    <>
      <Hero
        title="From documents to audit-ready posture in four steps"
        description="No new templates to learn — Sentinel GRC works with the policies and evidence your team already maintains."
      />

      <section className="mx-auto max-w-[900px] px-4 py-20 sm:px-6">
        <div className="space-y-4">
          {STEPS.map((item) => {
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

      <CTASection
        title="Bring your first document in under a minute"
        description="Sign in and upload a policy to see grounded coverage against your chosen framework."
      />
    </>
  );
}
