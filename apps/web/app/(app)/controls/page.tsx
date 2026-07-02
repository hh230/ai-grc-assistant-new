import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { ShieldCheck, TriangleAlert } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { CoverageBar } from "@/components/governance/CoverageBar";
import { ControlsExplorer } from "@/components/governance/ControlsExplorer";
import { LOGIN_PATH } from "@/lib/auth/config";
import { getActor } from "@/lib/auth/actor";
import { computeCoverage } from "@/lib/governance/coverage";

export const metadata: Metadata = {
  title: "Controls · Sentinel GRC",
};

export default async function ControlsPage() {
  const actor = await getActor();
  if (!actor) redirect(LOGIN_PATH);
  const report = await computeCoverage(actor);

  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          Governance
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Controls</h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">
          Every control across your frameworks, with live coverage from linked evidence and the gaps
          that need attention.
        </p>
      </header>

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <Card>
          <div className="flex items-center gap-2 text-foreground-muted">
            <ShieldCheck className="h-4 w-4" strokeWidth={1.75} />
            <span className="text-2xs uppercase tracking-wider">Coverage</span>
          </div>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {report.overall.coveragePct}%
          </p>
          <CoverageBar pct={report.overall.coveragePct} className="mt-2" />
          <p className="mt-2 text-2xs text-foreground-muted">
            {report.overall.coveredControls} of {report.overall.totalControls} controls covered
          </p>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-foreground-muted">
            <TriangleAlert className="h-4 w-4" strokeWidth={1.75} />
            <span className="text-2xs uppercase tracking-wider">Open gaps</span>
          </div>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {report.overall.gaps}
          </p>
          <p className="mt-2 text-2xs text-foreground-muted">controls with no linked evidence</p>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-foreground-muted">
            <span className="text-2xs uppercase tracking-wider">Evidence artifacts</span>
          </div>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {report.overall.evidenceCount}
          </p>
          <p className="mt-2 text-2xs text-foreground-muted">
            across {report.frameworks.length} frameworks
          </p>
        </Card>
      </div>

      <ControlsExplorer coverage={report} />
    </div>
  );
}
