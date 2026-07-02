"use client";

import { useState } from "react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, ShieldHalf, X } from "lucide-react";
import { cn } from "@/lib/utils";

const LINKS: { label: string; href: Route }[] = [
  { label: "Product", href: "/product" },
  { label: "Features", href: "/features" },
  { label: "Frameworks", href: "/frameworks-supported" },
  { label: "How it works", href: "/how-it-works" },
  { label: "Example reports", href: "/sample-reports" },
  { label: "FAQ", href: "/faq" },
];

export function MarketingNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-background/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5" onClick={() => setOpen(false)}>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-hairline-strong bg-surface-2 shadow-soft">
            <ShieldHalf className="h-[18px] w-[18px] text-accent" strokeWidth={1.75} />
          </div>
          <span className="text-sm font-semibold tracking-tight text-foreground">
            Sentinel GRC
          </span>
        </Link>

        <nav className="ms-4 hidden flex-1 items-center gap-1 lg:flex" aria-label="Main">
          {LINKS.map((link) => (
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
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="ms-auto hidden items-center gap-2 lg:flex">
          <LanguageSwitcherPlaceholder />
          <Link
            href="/login"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90"
          >
            Get started
          </Link>
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="ms-auto flex h-9 w-9 items-center justify-center rounded-lg border border-hairline bg-surface text-foreground-secondary lg:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
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
            {LINKS.map((link) => (
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
                {link.label}
              </Link>
            ))}
            <Link
              href="/login"
              onClick={() => setOpen(false)}
              className="mt-2 inline-flex h-10 items-center justify-center gap-1.5 rounded-lg bg-accent text-sm font-medium text-white shadow-glow"
            >
              Get started
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}

/**
 * Reserves the switcher's position in the nav so V2-P2's real EN/AR toggle (next-intl)
 * drops in without a layout shift. Presentational only until locale routing lands.
 */
function LanguageSwitcherPlaceholder() {
  return (
    <span
      className="inline-flex h-9 items-center rounded-lg border border-hairline px-3 text-xs font-medium text-foreground-muted"
      aria-hidden
      title="Language switching lands in the next milestone"
    >
      EN
    </span>
  );
}
