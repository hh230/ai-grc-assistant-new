"use client";

import { useLocale, useTranslations } from "next-intl";
import { Inbox } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { usePendingAccessRequests } from "@/hooks/useAccessRequests";
import { formatRelativeTime } from "@/lib/dashboard/relativeTime";
import type { AppLocale } from "@/i18n/routing";
import type { AccessRequest } from "@/lib/accessRequests/types";

interface AccessRequestListProps {
  selectedId: string | null;
  onSelect: (request: AccessRequest) => void;
}

export function AccessRequestList({ selectedId, onSelect }: AccessRequestListProps) {
  const t = useTranslations("accessRequestsWorkspace.list");
  const locale = useLocale() as AppLocale;
  const { data: requests, isLoading } = usePendingAccessRequests();

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
      ) : !requests || requests.length === 0 ? (
        <div className="flex flex-col items-center gap-2 p-10 text-center">
          <Inbox className="h-6 w-6 text-foreground-muted" strokeWidth={1.5} />
          <p className="text-sm text-foreground-secondary">{t("empty")}</p>
        </div>
      ) : (
        <ul className="divide-y divide-hairline">
          {requests.map((request) => (
            <li key={request.id}>
              <button
                type="button"
                onClick={() => onSelect(request)}
                className={`w-full px-5 py-4 text-start transition-colors hover:bg-surface-elevated ${
                  selectedId === request.id ? "bg-surface-elevated" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {request.organizationName}
                    </p>
                    <p className="truncate text-xs text-foreground-muted">
                      {request.name} · {request.email}
                    </p>
                  </div>
                  <Badge tone="warning">{t("statusPending")}</Badge>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-foreground-muted">
                  <span>{request.roleTitle}</span>
                  <span>{formatRelativeTime(request.createdAt, locale)}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
