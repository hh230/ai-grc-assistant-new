import { FileText, Download, Clock, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { REPORTS, type ReportItem } from "@/lib/data";

const statusMeta: Record<
  ReportItem["status"],
  { label: string; tone: "success" | "warning" | "accent" }
> = {
  ready: { label: "Ready", tone: "success" },
  scheduled: { label: "Scheduled", tone: "warning" },
  generating: { label: "Generating", tone: "accent" },
};

function ActionIcon({ status }: { status: ReportItem["status"] }) {
  if (status === "ready") return <Download className="h-4 w-4" strokeWidth={1.75} />;
  if (status === "generating") return <Loader2 className="h-4 w-4" strokeWidth={1.75} />;
  return <Clock className="h-4 w-4" strokeWidth={1.75} />;
}

export function ReportsSection() {
  return (
    <Card flush>
      <div className="p-5 pb-4">
        <SectionHeader
          title="Reports"
          description="Audit-ready deliverables & attestations"
          action={
            <button
              type="button"
              className="text-2xs font-medium text-accent-foreground hover:underline"
            >
              View library
            </button>
          }
        />
      </div>

      <div className="border-t border-hairline">
        {REPORTS.map((report, index) => {
          const status = statusMeta[report.status];
          return (
            <div
              key={report.id}
              className={`flex items-center gap-3 px-5 py-3.5 transition-colors duration-150 hover:bg-white/[0.02] ${
                index !== REPORTS.length - 1 ? "border-b border-hairline" : ""
              }`}
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-hairline bg-surface-2">
                <FileText className="h-4 w-4 text-foreground-secondary" strokeWidth={1.75} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground">{report.name}</p>
                <p className="mt-0.5 text-2xs text-foreground-muted">
                  {report.type} · {report.period} · {report.updated}
                </p>
              </div>
              <Badge tone={status.tone}>{status.label}</Badge>
              <button
                type="button"
                aria-label={report.status === "ready" ? "Download report" : "View report"}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-hairline text-foreground-muted transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-hover hover:text-foreground"
              >
                <ActionIcon status={report.status} />
              </button>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
