import { getTranslations } from "next-intl/server";
import { ChevronRight } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { Link } from "@/i18n/navigation";
import { getActor } from "@/lib/auth/actor";
import { getNeedsAttentionItems } from "@/lib/dashboard/needsAttention";
import { toneIconClasses } from "@/lib/design/tone";

/**
 * Band 2 of the dashboard (V2-P3 design proposal §11) — the section an executive scans
 * right after the topline scores: "what needs a decision today?" Sourced strictly from the
 * tenant's real framework coverage, risk register, and in-flight analyses (post-v2.0.1 audit
 * — previously a static illustrative dataset); renders nothing when there's genuinely
 * nothing to flag.
 */
export async function NeedsAttention() {
  const actor = await getActor();
  if (!actor) return null;

  const t = await getTranslations("dashboard.needsAttention");
  const tSeverity = await getTranslations("riskRegister.severity");
  const items = await getNeedsAttentionItems(actor);

  if (items.length === 0) return null;

  return (
    <Card flush>
      <div className="px-5 pt-5">
        <SectionHeader
          title={t("title")}
          description={t("description")}
          action={<Badge tone="danger">{t("count", { count: items.length })}</Badge>}
        />
      </div>
      <ul className="mt-4 divide-y divide-hairline">
        {items.map((item) => {
          const Icon = item.icon;
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
                    {t(item.titleKey, {
                      ...item.titleValues,
                      ...(item.severityKey ? { severity: tSeverity(item.severityKey) } : {}),
                    })}
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
