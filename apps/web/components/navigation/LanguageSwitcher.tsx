"use client";

import { useLocale } from "next-intl";
import { usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { cn } from "@/lib/utils";

const LOCALE_ARIA_LABEL: Record<string, string> = {
  ar: "التبديل إلى العربية",
  en: "Switch to English",
};

/**
 * Compact two-state AR/EN toggle (V2-P3 design proposal §6/§13). Preserves the current
 * page — switches only the locale segment of the URL.
 *
 * Uses a full page navigation, not next-intl's client-side `router.replace`: `<html
 * lang/dir>` lives in the true root layout (`app/layout.tsx`), which sits *above* the
 * `[locale]` segment (required so `app/api/*` stays unprefixed) — a soft client-side route
 * change re-renders the `[locale]` subtree but doesn't reliably refresh attributes set by
 * an ancestor layout, leaving `dir`/`lang`/the Arabic font class stale after switching.
 * Same rationale as `LoginForm`'s `window.location.assign`.
 */
export function LanguageSwitcher() {
  const locale = useLocale();
  const pathname = usePathname();

  return (
    <div
      role="group"
      aria-label="Language"
      className="flex h-9 shrink-0 items-center gap-0.5 rounded-lg border border-hairline bg-surface/60 p-0.5"
    >
      {routing.locales.map((loc) => {
        const active = loc === locale;
        return (
          <button
            key={loc}
            type="button"
            aria-current={active ? "true" : undefined}
            aria-label={LOCALE_ARIA_LABEL[loc]}
            onClick={() => {
              if (active) return;
              const search = typeof window !== "undefined" ? window.location.search : "";
              window.location.assign(`/${loc}${pathname === "/" ? "" : pathname}${search}`);
            }}
            className={cn(
              "rounded-md px-2 py-1 text-2xs font-medium uppercase tracking-wide transition-colors duration-150",
              active
                ? "bg-accent-soft text-accent-foreground"
                : "text-foreground-muted hover:text-foreground-secondary",
            )}
          >
            {loc}
          </button>
        );
      })}
    </div>
  );
}
