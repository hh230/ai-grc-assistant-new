"use client";

import { useTranslations } from "next-intl";
import { CircleDot } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type { NextAction, Priority } from "@/lib/analysis/types";

const PRIORITY_TONE: Record<Priority, "danger" | "warning" | "accent"> = {
  high: "danger",
  medium: "warning",
  low: "accent",
};

export function NextActions({ actions }: { actions: NextAction[] }) {
  const t = useTranslations("nextActions");
  if (actions.length === 0) return null;

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description", { count: actions.length })} />
      <ul className="mt-3 space-y-2.5">
        {actions.map((action, i) => (
          <li key={i} className="flex items-start justify-between gap-3 text-sm text-foreground-secondary">
            <span className="flex items-start gap-2">
              <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-foreground-muted" strokeWidth={1.75} />
              {action.action}
            </span>
            <Badge tone={PRIORITY_TONE[action.priority]} className="shrink-0">
              {t(`priority.${action.priority}`)}
            </Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}
