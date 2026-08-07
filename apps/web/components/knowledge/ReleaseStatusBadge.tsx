import { useTranslations } from "next-intl";
import type { ReleaseStatus } from "@/lib/knowledge/types";

/**
 * The five lifecycle states. `released` is styled as a *neutral* state on purpose: it means
 * eligible to be activated, not live, and colouring it like success is exactly how a reviewer
 * comes to believe a published release is already serving customers.
 */
const TONE: Record<ReleaseStatus, string> = {
  draft: "bg-surface-elevated text-foreground-muted",
  in_review: "bg-warning/10 text-warning",
  approved: "bg-accent-soft text-accent-foreground",
  released: "bg-surface-elevated text-foreground-secondary",
  deprecated: "bg-surface-elevated text-foreground-muted line-through",
};

export function ReleaseStatusBadge({ status }: { status: ReleaseStatus }) {
  const t = useTranslations("knowledgeConsole");
  return (
    <span className={`rounded-md px-1.5 py-0.5 font-medium ${TONE[status]}`}>
      {t(`status.${status}`)}
    </span>
  );
}
