"use client";

import { useTranslations } from "next-intl";
import { BookMarked } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";

export function References({ references }: { references: string[] }) {
  const t = useTranslations("references");
  if (references.length === 0) return null;

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description")} />
      <ul className="mt-3 space-y-1.5">
        {references.map((reference, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-foreground-secondary">
            <BookMarked className="mt-0.5 h-3.5 w-3.5 shrink-0 text-foreground-muted" strokeWidth={1.75} />
            {reference}
          </li>
        ))}
      </ul>
    </Card>
  );
}
