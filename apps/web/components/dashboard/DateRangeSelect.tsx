"use client";

import { ChevronDown } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import { Popover } from "@/components/ui/Popover";
import { cn } from "@/lib/utils";
import { DASHBOARD_RANGE_DAYS, type DashboardRangeDays } from "@/lib/dashboard/range";

const RANGE_LABEL_KEY: Record<DashboardRangeDays, string> = {
  7: "last7Days",
  30: "last30Days",
  90: "last90Days",
};

/** Filters every dashboard statistic and analysis result to the selected date range via
 *  the `?range=` search param, so the choice is server-rendered (no client fetch waterfall)
 *  and shareable/bookmarkable. */
export function DateRangeSelect({ rangeDays }: { rangeDays: DashboardRangeDays }) {
  const t = useTranslations("dashboard.pageHeader");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  function setRange(days: DashboardRangeDays) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("range", String(days));
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <Popover
      align="end"
      width={180}
      ariaLabel={t("rangeMenuLabel")}
      trigger={() => (
        <span className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2 hover:text-foreground">
          {t(RANGE_LABEL_KEY[rangeDays])}
          <ChevronDown className="h-3.5 w-3.5 text-foreground-muted" strokeWidth={1.75} />
        </span>
      )}
    >
      <div className="p-1">
        {DASHBOARD_RANGE_DAYS.map((days) => (
          <button
            key={days}
            type="button"
            onClick={() => setRange(days)}
            className={cn(
              "flex w-full items-center rounded-lg px-3 py-2 text-start text-sm transition-colors duration-150 hover:bg-surface",
              days === rangeDays ? "font-medium text-foreground" : "text-foreground-secondary",
            )}
          >
            {t(RANGE_LABEL_KEY[days])}
          </button>
        ))}
      </div>
    </Popover>
  );
}
