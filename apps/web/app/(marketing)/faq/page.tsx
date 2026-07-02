import type { Metadata } from "next";
import { Hero } from "@/components/marketing/Hero";
import { FAQAccordion } from "@/components/marketing/FAQAccordion";
import { CTASection } from "@/components/marketing/CTASection";

export const metadata: Metadata = {
  title: "FAQ · Sentinel GRC",
  description: "Answers to common questions about Sentinel GRC — data handling, human oversight, frameworks, and getting started.",
};

const FAQ_ITEMS = [
  {
    question: "Does Sentinel GRC replace our compliance team?",
    answer:
      "No. The platform is built as an assistant, not a replacement — it drafts, analyzes, and organizes work, but a qualified person on your team always reviews and approves anything consequential, like a policy publication or a risk acceptance.",
  },
  {
    question: "Where does the AI get its answers from?",
    answer:
      "Every answer is grounded in your own uploaded documents and the compliance framework text — never a general-purpose guess. If the platform doesn't have enough evidence to answer confidently, it tells you that instead of making something up.",
  },
  {
    question: "Which frameworks are supported?",
    answer:
      "Both regional and international standards, including NCA ECC, SAMA, and PDPL for Saudi Arabia, and ISO 27001, NIST CSF, CIS Controls, COBIT, and COSO internationally. New frameworks are added as configuration, not custom development.",
  },
  {
    question: "Is our data isolated from other organizations?",
    answer:
      "Yes. The platform is built multi-tenant from the ground up — every query, document, and AI retrieval is scoped strictly to your organization. Cross-tenant access isn't possible by design.",
  },
  {
    question: "Can we see how an AI-generated answer was produced?",
    answer:
      "Yes. Every AI-driven answer or recommendation is traceable back to the source documents and framework references it used, along with who approved any resulting action and when — built for external audit review.",
  },
  {
    question: "How do we get started?",
    answer:
      "Sign in, upload a policy or piece of evidence, and select the frameworks you're measured against. Coverage, gaps, and grounded answers are available within minutes.",
  },
];

export default function FAQPage() {
  return (
    <>
      <Hero
        title="Frequently asked questions"
        description="If your question isn't answered here, reach out and we'll walk you through it directly."
      />

      <section className="mx-auto max-w-[760px] px-4 pb-20 sm:px-6">
        <FAQAccordion items={FAQ_ITEMS} />
      </section>

      <CTASection
        title="Still have questions?"
        description="Sign in to explore a demo workspace, or reach out to talk through your specific frameworks and requirements."
      />
    </>
  );
}
