import type { Metadata } from "next";
import { Settings } from "lucide-react";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";
import { requireRoles } from "@/lib/auth/server";

export const metadata: Metadata = {
  title: "Settings · Sentinel GRC",
};

// Workspace administration is restricted to owners and admins (server-enforced RBAC).
export default async function SettingsPage() {
  await requireRoles("owner", "admin");
  return (
    <PlaceholderPage
      eyebrow="Account"
      title="Settings"
      description="Manage organization preferences, members, and workspace configuration."
      icon={Settings}
    />
  );
}
