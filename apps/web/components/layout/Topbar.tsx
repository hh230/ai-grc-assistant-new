"use client";

import { Menu, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { SearchBar } from "@/components/navigation/SearchBar";
import { OrgSwitcher } from "@/components/navigation/OrgSwitcher";
import { LanguageSwitcher } from "@/components/navigation/LanguageSwitcher";
import { NotificationsMenu } from "@/components/navigation/NotificationsMenu";
import { UserMenu } from "@/components/navigation/UserMenu";

interface TopbarProps {
  /** Opens the mobile navigation drawer (only shown below the `lg` breakpoint). */
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const t = useTranslations("topbar");

  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-background/70 backdrop-blur-xl">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
        {/* Mobile menu trigger — the desktop sidebar is always visible at lg+ */}
        <button
          type="button"
          onClick={onMenuClick}
          aria-label={t("openMenu")}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-hairline bg-surface/60 text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2 hover:text-foreground lg:hidden"
        >
          <Menu className="h-4 w-4" strokeWidth={1.75} />
        </button>

        <OrgSwitcher />
        <div className="mx-1 hidden h-5 w-px bg-hairline lg:block" />
        <div className="flex flex-1 justify-center lg:justify-start">
          <SearchBar />
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="hidden h-9 items-center gap-1.5 rounded-lg bg-foreground px-3 text-sm font-medium text-background transition-opacity duration-150 hover:opacity-90 sm:inline-flex"
          >
            <Plus className="h-4 w-4" strokeWidth={2} />
            {t("newMission")}
          </button>
          <LanguageSwitcher />
          <NotificationsMenu />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
