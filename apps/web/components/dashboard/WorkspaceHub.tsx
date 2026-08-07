"use client";

import { useTranslations } from "next-intl";
import { History } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Link } from "@/i18n/navigation";
import { useRecentlyViewed } from "@/lib/workspace/recentlyViewed";
import { QUICK_ACTIONS } from "@/lib/workspace/quickActions";
import { ENTITY_ICON } from "@/lib/search/entityMeta";

/**
 * Dashboard addition (V2-P3 Milestone 6, design proposal §9 Workspace concept) — added
 * as a new row after the existing Band 3 grid, not a restructure of it. Quick Actions live
 * in the section header (the same `action` slot `ActiveFrameworks`/`NeedsAttention` already
 * use); "Continue working" is the same recently-viewed mechanism that seeds the command
 * palette's empty state, so the two surfaces stay in sync with zero extra state.
 */
export function WorkspaceHub() {
  const t = useTranslations("workspace.continueWorking");
  const tActions = useTranslations("workspace.quickActions");
  const items = useRecentlyViewed();

  return (
    <Card flush>
      <div className="px-5 pt-5">
        <SectionHeader title={t("title")} description={t("description")} />
        <div className="mt-3 flex flex-wrap gap-1.5">
          {QUICK_ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.key}
                href={action.href}
                className="inline-flex h-7 items-center gap-1.5 rounded-full border border-hairline bg-surface/60 px-2.5 text-2xs font-medium text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
              >
                <Icon className="h-3 w-3" strokeWidth={1.75} />
                {tActions(action.key)}
              </Link>
            );
          })}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2">
            <History className="h-4 w-4 text-foreground-muted" strokeWidth={1.75} />
          </span>
          <p className="text-sm font-medium text-foreground">{t("emptyTitle")}</p>
          <p className="max-w-xs text-xs text-foreground-muted">{t("emptyDescription")}</p>
        </div>
      ) : (
        <ul className="mt-2 divide-y divide-hairline">
          {items.map((item) => {
            const Icon = ENTITY_ICON[item.type];
            return (
              <li key={`${item.type}:${item.id}`}>
                <Link
                  href={item.href}
                  className="flex items-center gap-3 px-5 py-3 transition-colors duration-150 hover:bg-white/[0.02]"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-hairline bg-surface-2">
                    <Icon className="h-4 w-4 text-foreground-secondary" strokeWidth={1.75} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-foreground">{item.title}</span>
                    {item.subtitle && (
                      <span className="block truncate text-2xs text-foreground-muted">
                        {item.subtitle}
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
