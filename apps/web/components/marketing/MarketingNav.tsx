"use client";

import { useState } from "react";
import { Menu, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { LanguageSwitcher } from "@/components/navigation/LanguageSwitcher";
import { cn } from "@/lib/utils";

const LINK_KEYS = [
  { key: "home", href: "/" },
  { key: "about", href: "/about" },
  { key: "howItWorks", href: "/how-it-works" },
  { key: "frameworks", href: "/frameworks-supported" },
  { key: "reports", href: "/sample-reports" },
  { key: "contact", href: "/contact" },
] as const;

export function MarketingNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const t = useTranslations("marketingNav");
  const tCommon = useTranslations("common");

  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-background/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center" onClick={() => setOpen(false)}>
          <span className="text-xl font-bold tracking-tight text-foreground">
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
            className="inline-flex h-9 items-center rounded-lg border border-hairline px-4 text-sm font-medium text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
          >
            {t("signIn")}
          </Link>
          <Link
            href="/request-access"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
          >
            {t("requestAccess")}
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
              className="mt-2 inline-flex h-10 items-center justify-center gap-1.5 rounded-lg border border-hairline text-sm font-medium text-foreground-secondary"
            >
              {t("signIn")}
            </Link>
            <Link
              href="/request-access"
              onClick={() => setOpen(false)}
              className="mt-2 inline-flex h-10 items-center justify-center gap-1.5 rounded-lg bg-accent text-sm font-medium text-white shadow-glow"
            >
              {t("requestAccess")}
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
