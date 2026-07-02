import {
  ClipboardCheck,
  FileCheck2,
  TriangleAlert,
  Sparkles,
  FileUp,
  FileBarChart,
  type LucideIcon,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { RECENT_ACTIVITIES, type Activity } from "@/lib/data";
import { cn } from "@/lib/utils";

const kindMeta: Record<Activity["kind"], { icon: LucideIcon; tone: string }> = {
  assessment: { icon: ClipboardCheck, tone: "text-success bg-success-soft" },
  policy: { icon: FileCheck2, tone: "text-accent-foreground bg-accent-soft" },
  risk: { icon: TriangleAlert, tone: "text-danger bg-danger-soft" },
  ai: { icon: Sparkles, tone: "text-accent-foreground bg-accent-soft" },
  evidence: { icon: FileUp, tone: "text-foreground-secondary bg-white/[0.05]" },
  report: { icon: FileBarChart, tone: "text-warning bg-warning-soft" },
};

export function RecentActivities() {
  return (
    <Card>
      <SectionHeader
        title="Recent Activities"
        description="Audit trail across agents and reviewers"
        action={
          <button
            type="button"
            className="text-2xs font-medium text-accent-foreground hover:underline"
          >
            Full audit log
          </button>
        }
      />

      <ol className="mt-5 space-y-1">
        {RECENT_ACTIVITIES.map((activity, index) => {
          const meta = kindMeta[activity.kind];
          const Icon = meta.icon;
          const isLast = index === RECENT_ACTIVITIES.length - 1;
          return (
            <li key={activity.id} className="relative flex gap-3.5 pb-4 last:pb-0">
              {!isLast && (
                <span
                  className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-hairline"
                  aria-hidden
                />
              )}
              <span
                className={cn(
                  "relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                  meta.tone,
                )}
              >
                <Icon className="h-4 w-4" strokeWidth={1.75} />
              </span>
              <div className="min-w-0 flex-1 pt-1">
                <p className="text-sm leading-snug text-foreground-secondary">
                  <span className="font-medium text-foreground">{activity.actor}</span>{" "}
                  {activity.action} <span className="text-foreground">{activity.target}</span>
                </p>
                <p className="mt-0.5 text-2xs text-foreground-muted">{activity.time}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
