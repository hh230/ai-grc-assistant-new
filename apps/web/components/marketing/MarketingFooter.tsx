"use client";

import { ShieldHalf } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

const COLUMNS = [
  {
    key: "product",
    links: [
      { key: "overview", href: "/product" },
      { key: "features", href: "/features" },
      { key: "howItWorks", href: "/how-it-works" },
    ],
  },
  {
    key: "compliance",
    links: [{ key: "exampleReports", href: "/sample-reports" }],
  },
  {
    key: "company",
    links: [
      { key: "faq", href: "/faq" },
      { key: "signIn", href: "/login" },
    ],
  },
] as const;

export function MarketingFooter() {
  const t = useTranslations("marketingFooter");
  const tCommon = useTranslations("common");

  return (
    <footer className="border-t border-hairline bg-canvas">
      <div className="mx-auto max-w-[1200px] px-4 py-14 sm:px-6">
        <div className="grid grid-cols-2 gap-10 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-hairline-strong bg-surface shadow-soft">
                <ShieldHalf className="h-[18px] w-[18px] text-accent" strokeWidth={1.75} />
              </div>
              <span className="text-sm font-semibold tracking-tight text-foreground">
                {tCommon("appName")}
              </span>
            </div>
            <p className="mt-3 max-w-[220px] text-xs text-foreground-muted">{t("tagline")}</p>
          </div>

          {COLUMNS.map((column) => (
            <div key={column.key}>
              <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
                {t(`columns.${column.key}.title`)}
              </p>
              <ul className="mt-3 space-y-2">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-foreground-secondary transition-colors duration-150 hover:text-foreground"
                    >
                      {t(`columns.${column.key}.${link.key}`)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 border-t border-hairline pt-6">
          <p className="text-2xs text-foreground-muted">
            {t("copyright", { year: new Date().getFullYear() })}
          </p>
        </div>
      </div>
    </footer>
  );
}
