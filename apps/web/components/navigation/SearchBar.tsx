"use client";

import { useEffect, useRef } from "react";
import { Search } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * Presentational command-search field. Focuses on ⌘K / Ctrl-K — a familiar
 * enterprise affordance (Linear, Vercel) — without opening a real palette.
 */
export function SearchBar() {
  const inputRef = useRef<HTMLInputElement>(null);
  const t = useTranslations("topbar");

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="group relative w-full max-w-md">
      <Search
        className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
        strokeWidth={1.75}
      />
      <input
        ref={inputRef}
        type="text"
        placeholder={t("searchPlaceholder")}
        aria-label={t("search")}
        className="h-9 w-full rounded-lg border border-hairline bg-surface/60 ps-9 pe-16 text-sm text-foreground placeholder:text-foreground-muted outline-none transition-colors duration-150 focus:border-hairline-strong focus:bg-surface-2"
      />
      <kbd className="pointer-events-none absolute end-2.5 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 rounded border border-hairline bg-white/[0.03] px-1.5 py-0.5 font-mono text-2xs text-foreground-muted sm:inline-flex">
        ⌘K
      </kbd>
    </div>
  );
}
