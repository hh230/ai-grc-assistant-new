import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { TrendPill } from "@/components/ui/TrendPill";
import { COMPLIANCE_PROGRESS } from "@/lib/data";

export function ComplianceProgress() {
  return (
    <Card>
      <SectionHeader
        title="Compliance Progress"
        description="Coverage vs. target by framework"
        action={
          <span className="flex items-center gap-1.5 text-2xs text-foreground-muted">
            <span className="h-px w-3 bg-white/30" />
            Target
          </span>
        }
      />
      <div className="mt-5 space-y-5">
        {COMPLIANCE_PROGRESS.map((item) => {
          const tone =
            item.value >= item.target ? "success" : item.value >= 80 ? "accent" : "warning";
          return (
            <div key={item.label}>
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-foreground-secondary">{item.label}</span>
                <div className="flex items-center gap-3">
                  <TrendPill trend="up" value={item.delta} goodWhen="up" />
                  <span className="font-mono tabular-nums text-foreground">
                    {item.value}
                    <span className="text-foreground-muted"> / {item.target}%</span>
                  </span>
                </div>
              </div>
              <ProgressBar value={item.value} target={item.target} tone={tone} className="mt-2" />
            </div>
          );
        })}
      </div>
    </Card>
  );
}
