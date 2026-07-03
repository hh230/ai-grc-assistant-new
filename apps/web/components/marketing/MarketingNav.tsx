"use client";

import { useState } from "react";
import { Menu, ShieldHalf, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { LanguageSwitcher } from "@/components/navigation/LanguageSwitcher";
import { cn } from "@/lib/utils";

const LINK_KEYS = [
  { key: "product", href: "/product" },
  { key: "features", href: "/features" },
  { key: "howItWorks", href: "/how-it-works" },
  { key: "exampleReports", href: "/sample-reports" },
  { key: "faq", href: "/faq" },
] as const;

export function MarketingNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const t = useTranslations("marketingNav");
  const tCommon = useTranslations("common");

  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-background/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5" onClick={() => setOpen(false)}>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-hairline-strong bg-surface-2 shadow-soft">
            <ShieldHalf className="h-[18px] w-[18px] text-accent" strokeWidth={1.75} />
          </div>
          <span className="text-sm font-semibold tracking-tight text-foreground">
            {tCommon("appName")}
          </span>
        </Link>

        <nav className="ms-4 hidden flex-1 items-center gap-1 lg:flex" aria-label="Main">
          {LINK_KEYS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "rounded-lg px-3 py-2 text-sm transition-colors duration-150",
                pathname === link.href
                  ? "bg-accent-soft text-accent-foreground"
                  : "text-foreground-secondary hover:bg-surface-2 hover:text-foreground",
              )}
            >
              {t(link.key)}
            </Link>
          ))}
        </nav>

        <div className="ms-auto hidden items-center gap-2 lg:flex">
          <LanguageSwitcher />
          <Link
            href="/login"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
          >
            {t("getStarted")}
          </Link>
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="ms-auto flex h-9 w-9 items-center justify-center rounded-lg border border-hairline bg-surface text-foreground-secondary lg:hidden"
          aria-label={open ? t("closeMenu") : t("openMenu")}
          aria-expanded={open}
        >
          {open ? (
            <X className="h-4 w-4" strokeWidth={1.75} />
          ) : (
            <Menu className="h-4 w-4" strokeWidth={1.75} />
          )}
        </button>
      </div>

      {open && (
        <div className="border-t border-hairline bg-background px-4 py-3 lg:hidden">
          <nav className="flex flex-col gap-0.5" aria-label="Main mobile">
            {LINK_KEYS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "rounded-lg px-3 py-2.5 text-sm",
                  pathname === link.href
                    ? "bg-accent-soft text-accent-foreground"
                    : "text-foreground-secondary hover:bg-surface-2 hover:text-foreground",
                )}
              >
                {t(link.key)}
              </Link>
            ))}
            <Link
              href="/login"
              onClick={() => setOpen(false)}
              className="mt-2 inline-flex h-10 items-center justify-center gap-1.5 rounded-lg bg-accent text-sm font-medium text-white shadow-glow"
            >
              {t("getStarted")}
            </Link>
            <div className="mt-2">
              <LanguageSwitcher />
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
