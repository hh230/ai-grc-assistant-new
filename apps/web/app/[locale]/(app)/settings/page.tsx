import type { Metadata } from "next";
import { Settings } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";
import { requireRoles } from "@/lib/auth/server";

export const metadata: Metadata = {
  title: "Settings · Rasheed",
};

// Workspace administration is restricted to owners and admins (server-enforced RBAC).
export default async function SettingsPage() {
  await requireRoles("owner", "admin");
  const t = await getTranslations("placeholders.settings");
  return (
    <PlaceholderPage
      eyebrow={t("eyebrow")}
      title={t("title")}
      description={t("description")}
      icon={Settings}
    />
  );
}
