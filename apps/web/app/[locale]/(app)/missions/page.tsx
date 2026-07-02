import type { Metadata } from "next";
import { Workflow } from "lucide-react";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export const metadata: Metadata = {
  title: "Missions · Sentinel GRC",
};

export default function MissionsPage() {
  return (
    <PlaceholderPage
      eyebrow="Overview"
      title="Missions"
      description="Track goal-directed GRC missions through their lifecycle, with plans, approval gates, and a full audit trail."
      icon={Workflow}
    />
  );
}
