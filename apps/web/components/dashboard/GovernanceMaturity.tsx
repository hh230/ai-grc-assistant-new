import { getTranslations } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { MaturityStars } from "@/components/governance/MaturityStars";
import { getCurrentMaturity } from "@/lib/planExecution/service";
import { MATURITY_DIMENSION_ORDER } from "@/lib/planExecution/types";
import type { ActorContext } from "@/lib/auth/actor";
import type { PlanDetail } from "@/lib/planExecution/types";

/**
 * Section 2 — where the organization stands, per dimension.
 *
 * Baseline against current, because a single figure hides the only interesting thing: whether
 * anything has moved since the plan started. Nothing is computed here — the baseline is the plan's
 * own record and the current reading comes from the engine that recalculates as actions complete.
 *
 * Deliberately five rows and no headline average. Averaging the dimensions would produce exactly
 * the kind of single number this page was redesigned to stop leading with, and an organization
 * that is strong on leadership and absent on cyber is not "medium".
 */
export async function GovernanceMaturity({
  actor,
  plan,
}: {
  actor: ActorContext;
  plan: PlanDetail;
}) {
  const t = await getTranslations("governanceMaturity");
  const tDimension = await getTranslations("planExecution.dimensions");
  // The engine returns an English label key ("initial", "established"); the same namespace the
  // plan page and the report already translate it through. Rendering it raw was leaving English
  // words in an Arabic page.
  const tLabel = await getTranslations("planExecution.maturityLabels");
  const current = await getCurrentMaturity(actor);

  return (
    <Card grain>
      <SectionHeader title={t("title")} description={t("description")} />
      <ul className="mt-3.5 space-y-1.5">
        {MATURITY_DIMENSION_ORDER.map((dimension) => {
          const baseline = plan.plan.maturityBaseline[dimension];
          if (!baseline) return null;
          // Falls back to the baseline when the engine has no live reading yet — a dimension the
          // plan recorded must not vanish from the page because a recalculation has not run.
          const now = current.maturity?.[dimension] ?? baseline;
          const moved = now.stars !== baseline.stars;
          return (
            <li
              key={dimension}
              className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-lg px-3 py-2 odd:bg-surface"
            >
              <span className="text-sm text-foreground-secondary">{tDimension(dimension)}</span>
              <span className="flex items-center gap-2 text-sm">
                {/* The baseline is shown struck-through only when it has actually changed —
                    otherwise the row would imply movement that has not happened. */}
                {moved && (
                  <>
                    <MaturityStars stars={baseline.stars} muted />
                    <span aria-hidden className="text-2xs text-foreground-muted">
                      →
                    </span>
                  </>
                )}
                <MaturityStars stars={now.stars} />
                <span className="text-2xs text-foreground-muted">
                  {tLabel(now.label as never)}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-2xs text-foreground-muted">{t("footnote")}</p>
    </Card>
  );
}
