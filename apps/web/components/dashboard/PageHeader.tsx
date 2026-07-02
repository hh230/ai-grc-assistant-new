"use client";

import { ChevronDown, Download, FileUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

export function PageHeader() {
  const t = useTranslations("dashboard.pageHeader");

  return (
    <div className="flex flex-col gap-4 pb-7 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="flex items-center gap-2 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          <span>Acme Financial Group</span>
          <span className="h-1 w-1 rounded-full bg-foreground-muted/50" />
          <span>Q2 2026</span>
        </div>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          {t("title")}
        </h1>
        <p className="mt-1 max-w-xl text-sm text-foreground-secondary">{t("subtitle")}</p>
      </div>

      <div className="flex items-center gap-2">
        {/* Period selector */}
        <button
          type="button"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2 hover:text-foreground"
        >
          {t("last90Days")}
          <ChevronDown className="h-3.5 w-3.5 text-foreground-muted" strokeWidth={1.75} />
        </button>

        {/* Export */}
        <button
          type="button"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2 hover:text-foreground"
        >
          <Download className="h-4 w-4" strokeWidth={1.75} />
          {t("export")}
        </button>

        {/* Primary CTA — Upload Contract → navigates to the upload experience */}
        <Link
          href="/upload"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90"
        >
          <FileUp className="h-4 w-4" strokeWidth={2} />
          {t("uploadContract")}
        </Link>
      </div>
    </div>
  );
}
