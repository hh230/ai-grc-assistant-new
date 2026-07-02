import type { Metadata } from "next";
import { LifeBuoy } from "lucide-react";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export const metadata: Metadata = {
  title: "Help & Support · Sentinel GRC",
};

export default function HelpPage() {
  return (
    <PlaceholderPage
      eyebrow="Account"
      title="Help & Support"
      description="Find documentation, contact support, and learn how to get the most out of the platform."
      icon={LifeBuoy}
    />
  );
}
