import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "@/i18n/navigation";
import { ShieldCheck, TriangleAlert } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { CoverageBar } from "@/components/governance/CoverageBar";
import { ControlsExplorer } from "@/components/governance/ControlsExplorer";
import { LOGIN_PATH } from "@/lib/auth/config";
import { getActor } from "@/lib/auth/actor";
import { computeCoverage } from "@/lib/governance/coverage";

export const metadata: Metadata = {
  title: "Controls · Rasheed",
};

export default async function ControlsPage() {
  const actor = await getActor();
  if (!actor) {
    redirect({ href: LOGIN_PATH, locale: await getLocale() });
  }
  const report = await computeCoverage(actor);
  const t = await getTranslations("controlsPage");

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">{t("description")}</p>
      </header>

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <Card>
          <div className="flex items-center gap-2 text-foreground-muted">
            <ShieldCheck className="h-4 w-4" strokeWidth={1.75} />
            <span className="text-2xs uppercase tracking-wider">{t("coverageLabel")}</span>
          </div>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {report.overall.coveragePct}%
          </p>
          <CoverageBar pct={report.overall.coveragePct} className="mt-2" />
          <p className="mt-2 text-2xs text-foreground-muted">
            {t("coverageSummary", {
              covered: report.overall.coveredControls,
              total: report.overall.totalControls,
            })}
          </p>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-foreground-muted">
            <TriangleAlert className="h-4 w-4" strokeWidth={1.75} />
            <span className="text-2xs uppercase tracking-wider">{t("openGapsLabel")}</span>
          </div>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {report.overall.gaps}
          </p>
          <p className="mt-2 text-2xs text-foreground-muted">{t("openGapsDescription")}</p>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-foreground-muted">
            <span className="text-2xs uppercase tracking-wider">{t("evidenceArtifactsLabel")}</span>
          </div>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {report.overall.evidenceCount}
          </p>
          <p className="mt-2 text-2xs text-foreground-muted">
            {t("evidenceArtifactsSummary", { count: report.frameworks.length })}
          </p>
        </Card>
      </div>

      <ControlsExplorer coverage={report} />
    </div>
  );
}
