"use client";

import { useLocale, useTranslations } from "next-intl";
import { FileText } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { usePendingRegulationVersions } from "@/hooks/useRegulationReview";
import { formatRelativeTime } from "@/lib/dashboard/relativeTime";
import type { AppLocale } from "@/i18n/routing";

interface PendingRegulationListProps {
  selectedVersionId: string | null;
  onSelect: (versionId: string) => void;
}

export function PendingRegulationList({
  selectedVersionId,
  onSelect,
}: PendingRegulationListProps) {
  const t = useTranslations("regulationReviewWorkspace.pendingList");
  const locale = useLocale() as AppLocale;
  const { data: versions, isLoading } = usePendingRegulationVersions();

  return (
    <Card flush>
      <div className="border-b border-hairline p-5">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h2 className="mt-1 text-sm font-semibold text-foreground">{t("title")}</h2>
      </div>

      {isLoading ? (
        <div className="space-y-3 p-5">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : !versions || versions.length === 0 ? (
        <div className="flex flex-col items-center gap-2 p-10 text-center">
          <FileText className="h-6 w-6 text-foreground-muted" strokeWidth={1.5} />
          <p className="text-sm text-foreground-secondary">{t("empty")}</p>
        </div>
      ) : (
        <ul className="divide-y divide-hairline">
          {versions.map((version) => (
            <li key={version.versionId}>
              <button
                type="button"
                onClick={() => onSelect(version.versionId)}
                className={`w-full px-5 py-4 text-start transition-colors hover:bg-surface-elevated ${
                  selectedVersionId === version.versionId ? "bg-surface-elevated" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {version.source.titleAr}
                    </p>
                    {version.source.titleEn && (
                      <p className="truncate text-xs text-foreground-muted">
                        {version.source.titleEn}
                      </p>
                    )}
                  </div>
                  <Badge tone="warning">{t("statusPending")}</Badge>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-foreground-muted">
                  <span>{version.versionLabel}</span>
                  <span>{formatRelativeTime(version.createdAt, locale)}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
