"use client";

import { useTranslations } from "next-intl";
import { Star } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { Link } from "@/i18n/navigation";
import { useFavorites } from "@/lib/workspace/favorites";
import { ENTITY_ICON } from "@/lib/search/entityMeta";

const MAX_VISIBLE = 6;

/** The Saved/Favorite Items surface (V2-P3 Milestone 6, design proposal §9). Reads the
 *  same localStorage-backed store the `FavoriteButton` star toggles write to — starring an
 *  item anywhere in the workspace (Analysis History, Risk Register, Policies, Evidence)
 *  shows up here immediately, no page reload. */
export function FavoritesPanel() {
  const t = useTranslations("workspace.favorites");
  const items = useFavorites();

  return (
    <Card flush>
      <div className="px-5 pt-5">
        <SectionHeader
          title={t("title")}
          description={t("description")}
          action={items.length > 0 ? <Badge tone="accent">{t("count", { count: items.length })}</Badge> : undefined}
        />
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2">
            <Star className="h-4 w-4 text-foreground-muted" strokeWidth={1.75} />
          </span>
          <p className="text-sm font-medium text-foreground">{t("emptyTitle")}</p>
          <p className="max-w-xs text-xs text-foreground-muted">{t("emptyDescription")}</p>
        </div>
      ) : (
        <ul className="mt-2 divide-y divide-hairline">
          {items.slice(0, MAX_VISIBLE).map((item) => {
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
