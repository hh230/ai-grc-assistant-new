import type { Metadata } from "next";
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

export default function FrameworksSupportedPage() {
  return (
    <>
      <Hero
        eyebrow="Frameworks"
        title="Built for regional and international regulators alike"
        description="Map one set of controls and evidence against every framework you're held to — Sentinel GRC's framework engine adds new standards without changing how you work."
      />

      <section className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {SUPPORTED_FRAMEWORKS.map((fw) => (
            <Card key={fw.shortName} className="p-7">
              <div className="flex items-start justify-between gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
                  <Library className="h-[18px] w-[18px] text-accent" strokeWidth={1.75} />
                </div>
                <Badge tone={fw.region === "Saudi Arabia" ? "accent" : "neutral"}>
                  {fw.region}
                </Badge>
              </div>
              <h3 className="mt-5 text-base font-semibold tracking-tight text-foreground">
                {fw.shortName}
              </h3>
              <p className="mt-1 text-xs text-foreground-muted">{fw.name}</p>
              {fw.description && (
                <p className="mt-3 text-sm leading-relaxed text-foreground-secondary">
                  {fw.description}
                </p>
              )}
            </Card>
          ))}
        </div>

        <p className="mx-auto mt-10 max-w-[560px] text-center text-sm text-foreground-muted">
          Don&apos;t see a framework you need? The framework engine represents every standard as
          structured data, so new frameworks are added without any change to how your
          controls, evidence, or reports work.
        </p>
      </section>

      <CTASection
        title="See your coverage across every framework at once"
        description="Sign in to view live coverage percentages, gaps, and evidence for your own workspace."
      />
    </>
  );
}
