import { ArrowUpRight } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ACTIVE_FRAMEWORKS, type ActiveFramework, type FrameworkStatus } from "@/lib/data";

const statusMeta: Record<FrameworkStatus, { key: string; tone: "success" | "warning" | "danger" }> =
  {
    compliant: { key: "compliant", tone: "success" },
    in_progress: { key: "inProgress", tone: "warning" },
    at_risk: { key: "atRisk", tone: "danger" },
  };

function FrameworkCard({
  framework,
  t,
}: {
  framework: ActiveFramework;
  t: Awaited<ReturnType<typeof getTranslations>>;
}) {
  const status = statusMeta[framework.status];
  const barTone = framework.status === "compliant" ? "success" : "warning";

  return (
    <Card className="group flex flex-col transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-hover">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-semibold tracking-tight text-foreground">
              {framework.code}
            </span>
            <ArrowUpRight className="h-3.5 w-3.5 text-foreground-muted opacity-0 transition-opacity duration-150 group-hover:opacity-100" />
          </div>
          <p className="mt-1 truncate text-xs text-foreground-muted">{framework.name}</p>
        </div>
        <Badge tone={status.tone} dot>
          {t(`status.${status.key}`)}
        </Badge>
      </div>

      <div className="mt-5">
        <div className="flex items-baseline justify-between">
          <span className="text-2xs uppercase tracking-wider text-foreground-muted">
            {t("coverage")}
          </span>
          <span className="font-mono text-sm font-medium tabular-nums text-foreground">
            {framework.coverage}%
          </span>
        </div>
        <ProgressBar value={framework.coverage} tone={barTone} className="mt-2" />
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-hairline pt-3 text-2xs text-foreground-muted">
        <span>
          <span className="text-foreground-secondary">{framework.controlsMet}</span> /{" "}
          {framework.controls} {t("controls")}
        </span>
        <span>{framework.region}</span>
      </div>
    </Card>
  );
}

export async function ActiveFrameworks() {
  const t = await getTranslations("dashboard.activeFrameworks");

  return (
    <div>
      <SectionHeader
        title={t("title")}
        description={t("description")}
        action={
          <button
            type="button"
            className="text-2xs font-medium text-accent-foreground hover:underline"
          >
            {t("viewAll", { count: 6 })}
          </button>
        }
      />
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        {ACTIVE_FRAMEWORKS.map((framework) => (
          <FrameworkCard key={framework.id} framework={framework} t={t} />
        ))}
      </div>
    </div>
  );
}
