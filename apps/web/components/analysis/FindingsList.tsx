import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type { AnalysisFinding, Severity } from "@/lib/analysis/types";
import { cn } from "@/lib/utils";

const SEVERITY_STYLES: Record<Severity, string> = {
  high: "bg-danger-soft text-danger",
  medium: "bg-warning-soft text-warning",
  low: "bg-accent-soft text-accent-foreground",
  info: "bg-surface-elevated text-foreground-muted",
};

const SEVERITY_RAIL: Record<Severity, string> = {
  high: "bg-danger",
  medium: "bg-warning",
  low: "bg-accent",
  info: "bg-foreground-muted",
};

export function FindingsList({ findings }: { findings: AnalysisFinding[] }) {
  if (findings.length === 0) return null;

  return (
    <Card flush>
      <div className="px-5 pt-4">
        <SectionHeader title="Findings" description={`${findings.length} grounded in the document text`} />
      </div>
      <div className="mt-3 divide-y divide-hairline">
        {findings.map((finding, i) => (
          <div key={i} className="relative flex gap-3 px-5 py-3.5">
            <span className={cn("w-0.5 shrink-0 rounded-full", SEVERITY_RAIL[finding.severity])} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-foreground">{finding.title}</p>
                <span
                  className={cn(
                    "shrink-0 rounded-full px-2 py-0.5 text-2xs font-medium capitalize",
                    SEVERITY_STYLES[finding.severity],
                  )}
                >
                  {finding.severity}
                </span>
              </div>
              <p className="mt-1 text-xs text-foreground-secondary">{finding.detail}</p>
              {finding.framework && (
                <p className="mt-1.5 text-2xs text-foreground-muted">Relates to: {finding.framework}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
