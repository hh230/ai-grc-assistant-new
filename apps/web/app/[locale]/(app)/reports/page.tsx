import type { Metadata } from "next";
import { requireSession } from "@/lib/auth/server";
import { ReportsWorkspace } from "@/components/reports/ReportsWorkspace";

export const metadata: Metadata = {
  title: "Reports · Sentinel GRC",
};

export default async function ReportsPage() {
  await requireSession();
  return (
    <div>
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          Risk &amp; Compliance
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Reports</h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">
          Audit-ready executive, compliance, and risk reports — aggregated from your live coverage,
          evidence, and risk data. Preview on screen, then export to PDF or Excel.
        </p>
      </header>

      <ReportsWorkspace />
    </div>
  );
}
