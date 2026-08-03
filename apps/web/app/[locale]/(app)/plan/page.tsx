import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { requireSession } from "@/lib/auth/server";
import { pageTitle } from "@/lib/pageMetadata";
import { PlanBoard } from "@/components/plan/PlanBoard";
import { Link } from "@/i18n/navigation";

export async function generateMetadata(): Promise<Metadata> {
  return pageTitle("planExecution.title");
}

/**
 * The Governance Plan Execution workspace (ADR 0066 §5, Phase 4) — the page a practitioner
 * returns to daily to move their organization's transformation plan forward: track status,
 * revert completion, attach evidence, and watch maturity recalculate as work actually happens.
 * Not a to-do list — a governance improvement program with a visible trajectory.
 */
export default async function PlanPage() {
  await requireSession();
  const t = await getTranslations("planExecution");

  return (
    <div className="mx-auto max-w-4xl">
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <p className="mt-1 text-sm text-foreground-secondary">{t("description")}</p>
        {/* Secondary, deliberately low-emphasis — re-running Discovery supersedes the active
            plan with a new version (ADR 0066 §3.1), not the primary action on this page. */}
        <Link
          href="/discovery?restart=1"
          className="mt-2 inline-block text-xs text-foreground-muted transition-colors duration-150 hover:text-foreground"
        >
          {t("runNewAssessment")}
        </Link>
      </header>

      <PlanBoard />
    </div>
  );
}
