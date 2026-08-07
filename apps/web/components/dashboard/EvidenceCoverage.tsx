import { getTranslations } from "next-intl/server";
import { ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Link } from "@/i18n/navigation";
import { computeCoverage } from "@/lib/governance/coverage";
import type { ActorContext } from "@/lib/auth/actor";

/**
 * Section 5 — what the organization can actually prove.
 *
 * One card where the old page had three (stat cards, progress bars, active frameworks), all
 * reading the same `computeCoverage` and all implying they were different measurements. The
 * calculation is untouched: a control counts as covered when at least one evidence artifact is
 * linked to it.
 *
 * Deliberately last of the five sections. Coverage is the axis a customer can do least about
 * today — it moves when evidence is attached, which is work the plan sends them to do.
 */
export async function EvidenceCoverage({ actor }: { actor: ActorContext }) {
  const t = await getTranslations("evidenceCoverage");
  const coverage = await computeCoverage(actor);

  return (
    <Card grain>
      <SectionHeader
        title={t("title")}
        description={t("description")}
        action={
          <Link
            href="/controls"
            className="inline-flex items-center gap-1 text-2xs text-foreground-muted transition-colors duration-150 hover:text-foreground"
          >
            {t("cta")}
            <ArrowRight className="h-3 w-3" strokeWidth={2} aria-hidden />
          </Link>
        }
      />

      <p className="mt-3 text-sm text-foreground-secondary">
        {t("summary", {
          covered: coverage.overall.coveredControls,
          total: coverage.overall.totalControls,
        })}
      </p>

      <ul className="mt-3.5 space-y-2">
        {coverage.frameworks.map((framework) => (
          <li key={framework.id} className="flex items-center gap-3">
            <span className="w-32 shrink-0 truncate text-2xs text-foreground-secondary">
              {framework.shortName}
            </span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface">
              <span
                className="block h-full rounded-full bg-accent"
                style={{ width: `${framework.coveragePct}%` }}
              />
            </span>
            <span className="w-10 shrink-0 text-end text-2xs text-foreground-muted">
              {framework.coveragePct}%
            </span>
          </li>
        ))}
      </ul>

      {coverage.overall.gaps > 0 && (
        <p className="mt-3 text-2xs text-foreground-muted">
          {t("gaps", { count: coverage.overall.gaps })}
        </p>
      )}
    </Card>
  );
}
