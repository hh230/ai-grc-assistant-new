import { BookMarked } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type { Priority, Recommendation } from "@/lib/analysis/types";

const PRIORITY_TONE: Record<Priority, "danger" | "warning" | "accent"> = {
  high: "danger",
  medium: "warning",
  low: "accent",
};

export function Recommendations({ recommendations }: { recommendations: Recommendation[] }) {
  if (recommendations.length === 0) return null;

  return (
    <Card flush>
      <div className="px-5 pt-4">
        <SectionHeader
          title="Recommended changes"
          description={`${recommendations.length} grounded in the document's findings`}
        />
      </div>
      <div className="mt-3 divide-y divide-hairline">
        {recommendations.map((rec, i) => (
          <div key={i} className="px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-medium text-foreground">{rec.change}</p>
              <Badge tone={PRIORITY_TONE[rec.priority]} className="shrink-0 capitalize">
                {rec.priority}
              </Badge>
            </div>
            <p className="mt-1.5 text-xs text-foreground-secondary">{rec.reason}</p>
            {rec.reference && (
              <p className="mt-2 inline-flex items-center gap-1.5 text-2xs text-foreground-muted">
                <BookMarked className="h-3 w-3" strokeWidth={1.75} />
                {rec.reference}
              </p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
