import type { Metadata } from "next";
import { Workflow, FileSearch, UserCheck } from "lucide-react";
import { Hero } from "@/components/marketing/Hero";
import { CTASection } from "@/components/marketing/CTASection";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "Product Overview · Sentinel GRC",
  description:
    "How Sentinel GRC organizes compliance work into governed missions, grounds every answer in evidence, and keeps a human in charge of consequential decisions.",
};

const SECTIONS = [
  {
    icon: Workflow,
    title: "Work runs as governed missions",
    description:
      "Instead of open-ended chat, every piece of compliance work — a gap analysis, an evidence sweep, a questionnaire response — runs as a mission with a clear goal, a visible plan, and a full history of what happened and why. You can see exactly what a mission is doing at any point, and step in whenever you need to.",
  },
  {
    icon: FileSearch,
    title: "Every answer is grounded and cited",
    description:
      "The platform never guesses on compliance matters. Answers are built from your own policies, evidence, and the framework text itself, and every claim carries a citation back to its source. If the evidence isn't there, the platform says so instead of filling the gap with a plausible-sounding answer.",
  },
  {
    icon: UserCheck,
    title: "A human approves anything consequential",
    description:
      "Drafting a policy, proposing a control mapping, or flagging a risk is something the platform can do on its own. Publishing that policy, accepting that risk, or signing off a control always requires a qualified person on your team to review the evidence and approve it explicitly.",
  },
] as const;

export default function ProductOverviewPage() {
  return (
    <>
      <Hero
        title="One platform for governance, risk, and compliance work"
        description="Sentinel GRC connects your controls, policies, evidence, and risk register to the frameworks you're measured against — and keeps every step traceable."
      />

      <section className="mx-auto max-w-[900px] space-y-16 px-4 py-20 sm:px-6">
        {SECTIONS.map((section, index) => {
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

      <CTASection
        title="Ready to see it against your own evidence?"
        description="Sign in with a demo workspace to explore missions, coverage, and reporting first-hand."
      />
    </>
  );
}
