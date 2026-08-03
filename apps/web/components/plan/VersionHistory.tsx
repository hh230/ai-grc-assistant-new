"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown, History } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { usePlanVersions } from "@/hooks/usePlanExecution";
import { cn } from "@/lib/utils";

const DIMENSION_ORDER = ["governance", "risk", "compliance", "cyber", "leadership"] as const;

/** How the user compares versions over time (ADR 0066 §3.1) — every approved plan is an
 * immutable snapshot; superseded versions carry the live maturity they had actually reached at
 * the moment the next version replaced them. */
export function VersionHistory() {
  const t = useTranslations("planExecution");
  const [open, setOpen] = useState(false);
  const { data: versions } = usePlanVersions();

  if (!versions || versions.length <= 1) return null;

  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 text-start"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-foreground">
          <History className="h-4 w-4 text-foreground-muted" strokeWidth={1.75} />
          {t("versions.title")}
        </span>
        <ChevronDown
          className={cn("h-4 w-4 text-foreground-muted transition-transform duration-150", open && "rotate-180")}
          strokeWidth={1.75}
        />
      </button>
      {open && (
        <ul className="mt-3 space-y-2 border-t border-hairline pt-3">
          {[...versions].reverse().map((version) => (
            <li
              key={version.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-hairline px-3 py-2 text-sm"
            >
              <span className="flex items-center gap-2">
                <span className="font-medium text-foreground">
                  {t("planVersion", { version: version.version })}
                </span>
                {version.status === "active" ? (
                  <Badge tone="accent">{t("versions.current")}</Badge>
                ) : (
                  <Badge tone="neutral">{t("versions.supersededOn")}</Badge>
                )}
              </span>
              {version.maturityAtSupersession && (
                <span className="flex items-center gap-1 text-2xs text-foreground-muted">
                  {DIMENSION_ORDER.map((d) => {
                    const rating = version.maturityAtSupersession?.[d];
                    if (!rating) return null;
                    return (
                      <span key={d} title={t(`dimensions.${d}` as never)}>
                        {"★".repeat(rating.stars)}
                        <span className="text-hairline-strong">{"☆".repeat(5 - rating.stars)}</span>
                      </span>
                    );
                  })}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
