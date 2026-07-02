import type { Metadata } from "next";
import { getLocale } from "next-intl/server";
import { ChevronRight, Library } from "lucide-react";
import { Link, redirect } from "@/i18n/navigation";
import { Card } from "@/components/ui/Card";
import { CoverageBar } from "@/components/governance/CoverageBar";
import { LOGIN_PATH } from "@/lib/auth/config";
import { getActor } from "@/lib/auth/actor";
import { computeCoverage } from "@/lib/governance/coverage";

export const metadata: Metadata = {
  title: "Frameworks · Sentinel GRC",
};

export default async function FrameworksPage() {
  const actor = await getActor();
  if (!actor) redirect({ href: LOGIN_PATH, locale: await getLocale() });
  const report = await computeCoverage(actor);

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          Governance
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Frameworks</h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">
          Compliance frameworks and their control coverage, computed from the evidence linked to
          each control.
        </p>
      </header>

      <Card className="mb-5 flex flex-wrap items-center gap-6">
        <Metric label="Frameworks" value={String(report.frameworks.length)} />
        <Metric label="Total controls" value={String(report.overall.totalControls)} />
        <Metric label="Controls covered" value={`${report.overall.coveredControls}`} />
        <Metric label="Overall coverage" value={`${report.overall.coveragePct}%`} accent />
        <div className="min-w-[160px] flex-1">
          <CoverageBar pct={report.overall.coveragePct} />
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {report.frameworks.map((framework) => (
          <Link key={framework.id} href={`/frameworks/${framework.id}`} className="group">
            <Card className="h-full transition-colors duration-150 group-hover:border-hairline-strong">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-hairline bg-surface-2">
                    <Library className="h-4 w-4 text-accent-foreground" strokeWidth={1.75} />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{framework.shortName}</p>
                    <p className="text-2xs text-foreground-muted">{framework.region}</p>
                  </div>
                </div>
                <ChevronRight
                  className="h-4 w-4 text-foreground-muted transition-transform duration-150 group-hover:translate-x-0.5"
                  strokeWidth={1.75}
                />
              </div>
              <p className="mt-3 line-clamp-1 text-xs text-foreground-muted">{framework.name}</p>
              <div className="mt-4 flex items-center justify-between text-xs">
                <span className="text-foreground-secondary">
                  {framework.covered}/{framework.total} controls
                </span>
                <span className="font-semibold text-foreground">{framework.coveragePct}%</span>
              </div>
              <CoverageBar pct={framework.coveragePct} className="mt-2" />
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <p
        className={
          accent
            ? "text-2xl font-semibold tracking-tight text-accent-foreground"
            : "text-2xl font-semibold tracking-tight text-foreground"
        }
      >
        {value}
      </p>
      <p className="text-2xs text-foreground-muted">{label}</p>
    </div>
  );
}
