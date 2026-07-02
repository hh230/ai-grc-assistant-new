"use client";

import { ShieldHalf } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { useSession } from "@/components/auth/SessionProvider";
import {
  PRIMARY_NAV,
  FOOTER_NAV,
  canSeeNavItem,
  isNavItemActive,
  type NavLink,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";

interface NavRowProps {
  item: NavLink;
  active: boolean;
  label: string;
  badgeLabel?: string;
  /** Invoked after navigation — used to close the mobile drawer. */
  onNavigate?: () => void;
}

function NavRow({ item, active, label, badgeLabel, onNavigate }: NavRowProps) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors duration-150",
        active
          ? "bg-white/[0.05] text-foreground"
          : "text-foreground-secondary hover:bg-white/[0.03] hover:text-foreground",
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4 shrink-0",
          active
            ? "text-accent-foreground"
            : "text-foreground-muted group-hover:text-foreground-secondary",
        )}
        strokeWidth={1.75}
      />
      <span className="truncate">{label}</span>
      {item.badge && (
        <span
          className={cn(
            "ms-auto rounded-full px-1.5 py-0.5 text-2xs font-medium",
            active || item.badge === "New"
              ? "bg-accent-soft text-accent-foreground"
              : "bg-white/[0.05] text-foreground-muted",
          )}
        >
          {badgeLabel ?? item.badge}
        </span>
      )}
    </Link>
  );
}

interface SidebarProps {
  /** Invoked when a nav item is clicked — lets the mobile drawer close itself. */
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const { user } = useSession();
  const roles = user.roles;
  const t = useTranslations("nav");

  // Hide nav items (and any group left empty) the current role may not access.
  const groups = PRIMARY_NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => canSeeNavItem(item, roles)),
  })).filter((group) => group.items.length > 0);
  const footerItems = FOOTER_NAV.filter((item) => canSeeNavItem(item, roles));

  return (
    <aside className="flex h-full w-[248px] shrink-0 flex-col border-e border-hairline bg-canvas">
      {/* Brand — also the fastest route to the dashboard */}
      <Link href="/dashboard" onClick={onNavigate} className="flex h-16 items-center gap-2.5 px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-hairline-strong bg-surface-2 shadow-soft">
          <ShieldHalf className="h-[18px] w-[18px] text-accent-foreground" strokeWidth={1.75} />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight text-foreground">Sentinel GRC</p>
          <p className="text-2xs text-foreground-muted">{t("brandTagline")}</p>
        </div>
      </Link>

      <div className="mx-5 h-px bg-hairline-x" />

      {/* Primary navigation */}
      <nav className="scrollbar-thin flex-1 space-y-6 overflow-y-auto px-3 py-5">
        {groups.map((group) => (
          <div key={group.labelKey}>
            <p className="px-2.5 pb-1.5 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
              {t(`groups.${group.labelKey}`)}
            </p>
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavRow
                  key={item.href}
                  item={item}
                  label={t(`items.${item.labelKey}`)}
                  badgeLabel={item.badge === "New" ? t("badgeNew") : undefined}
                  active={isNavItemActive(pathname, item.href)}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer navigation */}
      {footerItems.length > 0 && (
        <div className="space-y-0.5 border-t border-hairline px-3 py-3">
          {footerItems.map((item) => (
            <NavRow
              key={item.href}
              item={item}
              label={t(`items.${item.labelKey}`)}
              active={isNavItemActive(pathname, item.href)}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
    </aside>
  );
}
