import { Sparkles } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EXECUTIVE_SUMMARY } from "@/lib/data";

export function ExecutiveSummary() {
  return (
    <Card grain className="overflow-hidden">
      {/* Subtle accent fade at the top edge signals the AI-generated nature. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-accent-fade" />
      <div className="relative">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-soft">
              <Sparkles className="h-4 w-4 text-accent-foreground" strokeWidth={1.75} />
            </span>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">
              Executive Summary
            </h2>
          </div>
          <Badge tone="accent" dot>
            AI generated
          </Badge>
        </div>

        <p className="mt-4 max-w-3xl text-balance text-[15px] leading-relaxed text-foreground">
          {EXECUTIVE_SUMMARY.headline}
        </p>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-foreground-secondary">
          {EXECUTIVE_SUMMARY.body}
        </p>

        <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-hairline bg-hairline lg:grid-cols-4">
          {EXECUTIVE_SUMMARY.stats.map((stat) => (
            <div key={stat.label} className="bg-surface px-4 py-3.5">
              <p className="text-2xs uppercase tracking-wider text-foreground-muted">
                {stat.label}
              </p>
              <p className="mt-1 font-mono text-base font-medium tabular-nums text-foreground">
                {stat.value}
              </p>
            </div>
          ))}
        </div>

        <p className="mt-4 text-2xs text-foreground-muted">
          Grounded in 1,248 controls and 412 reviewed artifacts · every consequential change passed
          a human approval gate.
        </p>
      </div>
    </Card>
  );
}
