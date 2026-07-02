import type { Metadata } from "next";
import {
  ShieldCheck,
  FileText,
  Library,
  TriangleAlert,
  FolderArchive,
  FileBarChart,
  MessageSquareText,
  ClipboardList,
} from "lucide-react";
import { Hero } from "@/components/marketing/Hero";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { CTASection } from "@/components/marketing/CTASection";

export const metadata: Metadata = {
  title: "Features · Sentinel GRC",
  description: "Every feature of the Sentinel GRC governance, risk, and compliance workspace.",
};

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Controls",
    description:
      "A live view of every control across your frameworks, its coverage status, and the evidence backing it.",
  },
  {
    icon: FileText,
    title: "Policies",
    description:
      "Author and review policies with a clear draft → review → published workflow and control mapping.",
  },
  {
    icon: Library,
    title: "Frameworks",
    description:
      "Coverage and gaps tracked per framework, with cross-framework mapping so one piece of evidence can satisfy several regulators at once.",
  },
  {
    icon: TriangleAlert,
    title: "Risk register",
    description:
      "Score risks with a standard likelihood × impact matrix, track mitigation, and require sign-off before any risk is accepted.",
  },
  {
    icon: FolderArchive,
    title: "Evidence",
    description:
      "Upload, tag, and version evidence, and link it directly to the controls and policies it supports.",
  },
  {
    icon: MessageSquareText,
    title: "AI workspace",
    description:
      "Ask questions about your compliance posture in plain language and get grounded, cited answers.",
  },
  {
    icon: ClipboardList,
    title: "Assessments",
    description: "Run gap analyses and coverage assessments against any supported framework.",
  },
  {
    icon: FileBarChart,
    title: "Reports",
    description:
      "Generate executive, compliance, and risk reports on demand, ready to export for auditors and leadership.",
  },
] as const;

export default function FeaturesPage() {
  return (
    <>
      <Hero
        title="Everything your compliance team needs in one workspace"
        description="Controls, policies, risk, evidence, and reporting — connected, not scattered across spreadsheets and email threads."
      />

      <section className="mx-auto max-w-[1200px] px-4 py-20 sm:px-6">
        <FeatureGrid items={FEATURES} />
      </section>

      <CTASection
        title="See it running against real evidence"
        description="Every feature above is grounded in your own documents from the moment you sign in."
      />
    </>
  );
}
