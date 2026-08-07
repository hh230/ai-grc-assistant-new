import { Download, FileUp } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { getSession } from "@/lib/auth/server";
import { DateRangeSelect } from "@/components/dashboard/DateRangeSelect";
import type { DashboardRangeDays } from "@/lib/dashboard/metrics";

export async function PageHeader({ rangeDays }: { rangeDays: DashboardRangeDays }) {
  const t = await getTranslations("dashboard.pageHeader");
  const session = await getSession();

  return (
    <div className="flex flex-col gap-4 pb-7 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="flex items-center gap-2 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          <span>{session?.organizationName}</span>
        </div>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          {t("title")}
        </h1>
        <p className="mt-1 max-w-xl text-sm text-foreground-secondary">{t("subtitle")}</p>
      </div>

      <div className="flex items-center gap-2">
        {/* Period selector */}
        <DateRangeSelect rangeDays={rangeDays} />

        {/* Export */}
        <a
          href={`/api/dashboard/export?range=${rangeDays}`}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2 hover:text-foreground"
        >
          <Download className="h-4 w-4" strokeWidth={1.75} />
          {t("export")}
        </a>

        {/* Primary CTA — Add Document → navigates to the upload experience */}
        <Link
          href="/upload"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
        >
          <FileUp className="h-4 w-4" strokeWidth={2} />
          {t("uploadContract")}
        </Link>
      </div>
    </div>
  );
}
