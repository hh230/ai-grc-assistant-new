import { getTranslations } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { RISK_DISTRIBUTION, RISK_SCORE, type RiskSlice } from "@/lib/data";

const toneColor: Record<RiskSlice["tone"], string> = {
  accent: "var(--accent)",
  warning: "var(--warning)",
  danger: "var(--danger)",
  success: "var(--success)",
  neutral: "var(--neutral)",
};

const SIZE = 168;
const STROKE = 16;
const RADIUS = (SIZE - STROKE) / 2;
const CIRC = 2 * Math.PI * RADIUS;
const GAP = 2; // px gap between slices for a refined, segmented look

export async function RiskDistribution() {
  const t = await getTranslations("dashboard.riskDistribution");
  const tScoreCards = await getTranslations("dashboard.scoreCards");
  let cumulative = 0;

  return (
    <Card>
      <SectionHeader title={t("title")} description={t("description")} />

      <div className="mt-5 flex items-center gap-6">
        <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
          <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="-rotate-90">
            {RISK_DISTRIBUTION.map((slice) => {
              const length = (slice.value / 100) * CIRC;
              const dash = Math.max(0, length - GAP);
              const circle = (
                <circle
                  key={slice.label}
                  cx={SIZE / 2}
                  cy={SIZE / 2}
                  r={RADIUS}
                  fill="none"
                  stroke={toneColor[slice.tone]}
                  strokeWidth={STROKE}
                  strokeDasharray={`${dash} ${CIRC - dash}`}
                  strokeDashoffset={-(cumulative / 100) * CIRC}
                />
              );
              cumulative += slice.value;
              return circle;
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono text-2xl font-medium tabular-nums text-foreground">
              {RISK_SCORE.value}
            </span>
            <span className="text-2xs uppercase tracking-wider text-foreground-muted">
              {tScoreCards("riskBand")}
            </span>
          </div>
        </div>

        <ul className="min-w-0 flex-1 space-y-2.5">
          {RISK_DISTRIBUTION.map((slice) => (
            <li key={slice.label} className="flex items-center gap-2.5 text-xs">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-[3px]"
                style={{ backgroundColor: toneColor[slice.tone] }}
              />
              <span className="min-w-0 flex-1 truncate text-foreground-secondary">
                {t(`categories.${slice.labelKey}`)}
              </span>
              <span className="font-mono tabular-nums text-foreground">{slice.value}%</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
