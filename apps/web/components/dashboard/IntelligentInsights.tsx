import { getTranslations } from "next-intl/server";
import { ChevronRight, TriangleAlert, FileText, Sparkles, TrendingUp, ListChecks } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { Link } from "@/i18n/navigation";
import { getActor } from "@/lib/auth/actor";
import { getLiveInsights, type LiveInsight } from "@/lib/dashboard/liveInsights";
import { toneIconClasses } from "@/lib/design/tone";

const ICON: Record<LiveInsight["icon"], typeof TriangleAlert> = {
  risk: TriangleAlert,
  document: FileText,
  analysis: Sparkles,
  trend: TrendingUp,
  action: ListChecks,
};

/**
 * Real-workspace counterpart to `NeedsAttention` (which renders the static illustrative
 * dataset for the investor-demo narrative — CLAUDE.md "don't redesign the UI"). This reads
 * the signed-in tenant's actual risks, documents, and analyses and only renders when that
 * data exists, so it stays silent for a fresh tenant rather than showing an empty card.
 */
export async function IntelligentInsights() {
  const actor = await getActor();
  if (!actor) return null;

  const t = await getTranslations("dashboard.intelligentInsights");
  const items = await getLiveInsights(actor);
  if (items.length === 0) return null;

  return (
    <Card flush>
      <div className="px-5 pt-5">
        <SectionHeader
          title={t("title")}
          description={t("description")}
          action={<Badge tone="accent" dot>{t("badge")}</Badge>}
        />
      </div>
      <ul className="mt-4 divide-y divide-hairline">
        {items.map((item) => {
          const Icon = ICON[item.icon];
          return (
            <li key={item.id}>
              <Link
                href={item.href}
                className="group flex items-center gap-3.5 px-5 py-3.5 transition-colors duration-150 hover:bg-white/[0.02]"
              >
                <span
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${toneIconClasses[item.tone]}`}
                >
                  <Icon className="h-4 w-4" strokeWidth={1.75} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-foreground">
                    {t(item.titleKey, item.titleValues)}
                  </span>
                  <span className="block truncate text-2xs text-foreground-muted">
                    {t(item.detailKey, item.detailValues)}
                  </span>
                </span>
                <ChevronRight
                  className="h-4 w-4 shrink-0 text-foreground-muted opacity-0 transition-opacity duration-150 group-hover:opacity-100 flip-rtl"
                  strokeWidth={1.75}
                />
              </Link>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
