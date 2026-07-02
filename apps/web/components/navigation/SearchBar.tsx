"use client";

import { Search } from "lucide-react";
import { useTranslations } from "next-intl";

interface SearchBarProps {
  onClick: () => void;
}

/**
 * The Topbar's global-search trigger. Same field-shaped affordance as before (icon,
 * placeholder text, ⌘K hint) — it now opens the real command palette (`CommandPalette`)
 * instead of just focusing a local, non-functional input.
 */
export function SearchBar({ onClick }: SearchBarProps) {
  const t = useTranslations("topbar");

  return (
    <button
      type="button"
      onClick={onClick}
      aria-haspopup="dialog"
      aria-label={t("search")}
      className="group relative flex h-9 w-full max-w-md items-center rounded-lg border border-hairline bg-surface/60 ps-9 pe-16 text-start text-sm text-foreground-muted transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2"
    >
      <Search
        className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
        strokeWidth={1.75}
      />
      <span className="truncate">{t("searchPlaceholder")}</span>
      <kbd className="pointer-events-none absolute end-2.5 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 rounded border border-hairline bg-white/[0.03] px-1.5 py-0.5 font-mono text-2xs text-foreground-muted sm:inline-flex">
        ⌘K
      </kbd>
    </button>
  );
}
