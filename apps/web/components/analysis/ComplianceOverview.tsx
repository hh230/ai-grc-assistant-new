"use client";

import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";

export function ComplianceOverview({ overview }: { overview?: string }) {
  const t = useTranslations("complianceOverview");
  if (!overview) return null;

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description")} />
      <p className="mt-3 text-sm leading-relaxed text-foreground-secondary">{overview}</p>
    </Card>
  );
}
