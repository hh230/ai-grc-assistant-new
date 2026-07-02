import type { Metadata } from "next";
import { ClipboardList } from "lucide-react";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export const metadata: Metadata = {
  title: "Assessments · Sentinel GRC",
};

export default function AssessmentsPage() {
  return (
    <PlaceholderPage
      eyebrow="Risk & Compliance"
      title="Assessments"
      description="Run gap analyses and coverage assessments against one or more frameworks, with confidence and provenance."
      icon={ClipboardList}
    />
  );
}
