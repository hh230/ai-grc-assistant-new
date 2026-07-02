import { getTranslations } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { RECENT_ASSESSMENTS, type Assessment } from "@/lib/data";

const statusMeta: Record<Assessment["status"], { key: string; tone: "success" | "accent" | "warning" }> =
  {
    completed: { key: "completed", tone: "success" },
    in_review: { key: "inReview", tone: "accent" },
    in_progress: { key: "inProgress", tone: "warning" },
  };

function ScorePill({ score }: { score: number | null }) {
  if (score === null) {
    return <span className="font-mono text-xs tabular-nums text-foreground-muted">—</span>;
  }
  const tone = score >= 85 ? "text-success" : score >= 75 ? "text-foreground" : "text-warning";
  return <span className={`font-mono text-xs font-medium tabular-nums ${tone}`}>{score}</span>;
}

export async function RecentAssessments() {
  const t = await getTranslations("dashboard.recentAssessments");

  return (
    <Card flush>
      <div className="p-5 pb-4">
        <SectionHeader
          title={t("title")}
          description={t("description")}
          action={
            <button
              type="button"
              className="text-2xs font-medium text-accent-foreground hover:underline"
            >
              {t("viewAll")}
            </button>
          }
        />
      </div>

      {/* Column header */}
      <div className="grid grid-cols-12 gap-3 border-y border-hairline px-5 py-2 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
        <span className="col-span-6">{t("columns.assessment")}</span>
        <span className="col-span-2">{t("columns.owner")}</span>
        <span className="col-span-2 text-center">{t("columns.status")}</span>
        <span className="col-span-1 text-end">{t("columns.score")}</span>
        <span className="col-span-1 text-end">{t("columns.updated")}</span>
      </div>

      <div>
        {RECENT_ASSESSMENTS.map((a, index) => {
          const status = statusMeta[a.status];
          return (
            <div
              key={a.id}
              className={`grid grid-cols-12 items-center gap-3 px-5 py-3 transition-colors duration-150 hover:bg-white/[0.02] ${
                index !== RECENT_ASSESSMENTS.length - 1 ? "border-b border-hairline" : ""
              }`}
            >
              <div className="col-span-6 min-w-0">
                <p className="truncate text-sm text-foreground">{a.name}</p>
                <p className="mt-0.5 font-mono text-2xs text-foreground-muted">{a.framework}</p>
              </div>
              <span className="col-span-2 truncate text-xs text-foreground-secondary">
                {a.owner}
              </span>
              <div className="col-span-2 flex justify-center">
                <Badge tone={status.tone}>{t(`status.${status.key}`)}</Badge>
              </div>
              <div className="col-span-1 text-end">
                <ScorePill score={a.score} />
              </div>
              <span className="col-span-1 text-end text-2xs text-foreground-muted">
                {a.updated}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
