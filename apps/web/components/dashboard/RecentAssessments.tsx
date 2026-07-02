import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { RECENT_ASSESSMENTS, type Assessment } from "@/lib/data";

const statusMeta: Record<
  Assessment["status"],
  { label: string; tone: "success" | "accent" | "warning" }
> = {
  completed: { label: "Completed", tone: "success" },
  in_review: { label: "In review", tone: "accent" },
  in_progress: { label: "In progress", tone: "warning" },
};

function ScorePill({ score }: { score: number | null }) {
  if (score === null) {
    return <span className="font-mono text-xs tabular-nums text-foreground-muted">—</span>;
  }
  const tone = score >= 85 ? "text-success" : score >= 75 ? "text-foreground" : "text-warning";
  return <span className={`font-mono text-xs font-medium tabular-nums ${tone}`}>{score}</span>;
}

export function RecentAssessments() {
  return (
    <Card flush>
      <div className="p-5 pb-4">
        <SectionHeader
          title="Recent Assessments"
          description="Latest control reviews across frameworks"
          action={
            <button
              type="button"
              className="text-2xs font-medium text-accent-foreground hover:underline"
            >
              View all
            </button>
          }
        />
      </div>

      {/* Column header */}
      <div className="grid grid-cols-12 gap-3 border-y border-hairline px-5 py-2 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
        <span className="col-span-6">Assessment</span>
        <span className="col-span-2">Owner</span>
        <span className="col-span-2 text-center">Status</span>
        <span className="col-span-1 text-right">Score</span>
        <span className="col-span-1 text-right">Updated</span>
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
                <Badge tone={status.tone}>{status.label}</Badge>
              </div>
              <div className="col-span-1 text-right">
                <ScorePill score={a.score} />
              </div>
              <span className="col-span-1 text-right text-2xs text-foreground-muted">
                {a.updated}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
