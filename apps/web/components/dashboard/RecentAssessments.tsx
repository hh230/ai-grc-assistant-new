import { ClipboardList } from "lucide-react";
import { getTranslations, getLocale } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Link } from "@/i18n/navigation";
import { getActor } from "@/lib/auth/actor";
import { listAnalyses } from "@/lib/analysis/service";
import { formatRelativeTime } from "@/lib/dashboard/relativeTime";
import type { AppLocale } from "@/i18n/routing";
import type { AnalysisStatus } from "@/lib/analysis/types";

const statusMeta: Record<
  AnalysisStatus,
  { key: string; tone: "success" | "accent" | "warning" | "danger" }
> = {
  processed: { key: "completed", tone: "success" },
  processing: { key: "inProgress", tone: "warning" },
  queued: { key: "inProgress", tone: "warning" },
  failed: { key: "failed", tone: "danger" },
};

function ScorePill({ score }: { score: number | null | undefined }) {
  if (score == null) {
    return <span className="font-mono text-xs tabular-nums text-foreground-muted">—</span>;
  }
  const tone = score >= 85 ? "text-success" : score >= 75 ? "text-foreground" : "text-warning";
  return <span className={`font-mono text-xs font-medium tabular-nums ${tone}`}>{score}</span>;
}

export async function RecentAssessments() {
  const t = await getTranslations("dashboard.recentAssessments");
  const locale = (await getLocale()) as AppLocale;
  const actor = await getActor();
  const analyses = actor ? await listAnalyses(actor) : [];
  const items = analyses.slice(0, 6);

  return (
    <Card flush>
      <div className="p-5 pb-4">
        <SectionHeader
          title={t("title")}
          description={t("description")}
          action={
            <Link href="/analysis" className="text-2xs font-medium text-accent-foreground hover:underline">
              {t("viewAll")}
            </Link>
          }
        />
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-elevated">
            <ClipboardList className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">{t("emptyTitle")}</p>
            <p className="max-w-xs text-xs text-foreground-muted">{t("emptyDescription")}</p>
          </div>
        </div>
      ) : (
        <>
          {/* Column header */}
          <div className="grid grid-cols-12 gap-3 border-y border-hairline px-5 py-2 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
            <span className="col-span-6">{t("columns.assessment")}</span>
            <span className="col-span-2">{t("columns.owner")}</span>
            <span className="col-span-2 text-center">{t("columns.status")}</span>
            <span className="col-span-1 text-end">{t("columns.score")}</span>
            <span className="col-span-1 text-end">{t("columns.updated")}</span>
          </div>

          <div>
            {items.map((a, index) => {
              const status = statusMeta[a.status];
              const primaryFramework = a.frameworks[0]?.framework;
              const frameworkLabel = primaryFramework
                ? a.frameworks.length > 1
                  ? `${primaryFramework} +${a.frameworks.length - 1}`
                  : primaryFramework
                : "—";
              return (
                <Link
                  key={a.id}
                  href={`/analysis?doc=${a.documentId}`}
                  className={`grid grid-cols-12 items-center gap-3 px-5 py-3 transition-colors duration-150 hover:bg-white/[0.02] ${
                    index !== items.length - 1 ? "border-b border-hairline" : ""
                  }`}
                >
                  <div className="col-span-6 min-w-0">
                    <p className="truncate text-sm text-foreground">{a.title}</p>
                    <p className="mt-0.5 font-mono text-2xs text-foreground-muted">
                      {frameworkLabel}
                    </p>
                  </div>
                  <span className="col-span-2 truncate text-xs text-foreground-secondary">
                    {a.requestedByName}
                  </span>
                  <div className="col-span-2 flex justify-center">
                    <Badge tone={status.tone}>{t(`status.${status.key}`)}</Badge>
                  </div>
                  <div className="col-span-1 text-end">
                    <ScorePill score={a.complianceScore} />
                  </div>
                  <span className="col-span-1 text-end text-2xs text-foreground-muted">
                    {formatRelativeTime(a.completedAt ?? a.updatedAt, locale)}
                  </span>
                </Link>
              );
            })}
          </div>
        </>
      )}
    </Card>
  );
}
