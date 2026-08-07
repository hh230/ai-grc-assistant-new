import { ShieldAlert } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { getActor } from "@/lib/auth/actor";
import { listRisks } from "@/lib/risk/service";
import { scoreOf, severityOf, type Severity } from "@/lib/risk/types";

const toneColor: Record<Severity, string> = {
  critical: "var(--danger)",
  high: "var(--danger)",
  medium: "var(--warning)",
  low: "var(--success)",
};

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

const SIZE = 168;
const STROKE = 16;
const RADIUS = (SIZE - STROKE) / 2;
const CIRC = 2 * Math.PI * RADIUS;
const GAP = 2; // px gap between slices for a refined, segmented look

/** Residual risk exposure by severity — computed from the tenant's own risk register
 * (post-v2.0.1 audit; previously a static illustrative dataset unrelated to any real
 * tenant). Renders an honest empty state when the register has no risks yet, rather than
 * fabricated percentages. */
export async function RiskDistribution() {
  const t = await getTranslations("dashboard.riskDistribution");
  const tSeverity = await getTranslations("riskRegister.severity");
  const actor = await getActor();
  if (!actor) return null;

  const risks = await listRisks(actor);
  const total = risks.length;

  if (total === 0) {
    return (
      <Card>
        <SectionHeader title={t("title")} description={t("description")} />
        <div className="mt-5 flex flex-col items-center gap-3 py-8 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-elevated">
            <ShieldAlert className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
          </div>
          <p className="text-sm font-medium text-foreground">{t("emptyTitle")}</p>
        </div>
      </Card>
    );
  }

  const counts: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const risk of risks) {
    counts[severityOf(scoreOf(risk.likelihood, risk.impact))] += 1;
  }
  const slices = SEVERITIES.map((severity) => ({
    severity,
    pct: Math.round((counts[severity] / total) * 100),
  }));

  let cumulative = 0;

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description")} />

      <div className="mt-5 flex items-center gap-6">
        <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
          <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="-rotate-90">
            {slices.map((slice) => {
              const length = (slice.pct / 100) * CIRC;
              const dash = Math.max(0, length - GAP);
              const circle = (
                <circle
                  key={slice.severity}
                  cx={SIZE / 2}
                  cy={SIZE / 2}
                  r={RADIUS}
                  fill="none"
                  stroke={toneColor[slice.severity]}
                  strokeWidth={STROKE}
                  strokeDasharray={`${dash} ${CIRC - dash}`}
                  strokeDashoffset={-(cumulative / 100) * CIRC}
                />
              );
              cumulative += slice.pct;
              return circle;
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono text-2xl font-medium tabular-nums text-foreground">
              {total}
            </span>
            <span className="text-2xs uppercase tracking-wider text-foreground-muted">
              {t("totalRisks")}
            </span>
          </div>
        </div>

        <ul className="min-w-0 flex-1 space-y-2.5">
          {slices.map((slice) => (
            <li key={slice.severity} className="flex items-center gap-2.5 text-xs">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-[3px]"
                style={{ backgroundColor: toneColor[slice.severity] }}
              />
              <span className="min-w-0 flex-1 truncate text-foreground-secondary">
                {tSeverity(slice.severity)}
              </span>
              <span className="font-mono tabular-nums text-foreground">{slice.pct}%</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
