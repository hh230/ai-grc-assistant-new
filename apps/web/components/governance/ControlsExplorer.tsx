"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CheckCircle2, CircleDashed, FileText, Loader2, Search } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { useEvidence } from "@/hooks/useEvidence";
import { getControl } from "@/lib/frameworks/catalog";
import type { CoverageReport } from "@/lib/governance/coverage";
import { cn } from "@/lib/utils";

type StatusFilter = "all" | "covered" | "gap";

export function ControlsExplorer({ coverage }: { coverage: CoverageReport }) {
  const [frameworkId, setFrameworkId] = useState<string>("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [activeControl, setActiveControl] = useState<string | null>(null);

  const rows = useMemo(() => {
    const flat = coverage.frameworks.flatMap((framework) =>
      framework.controls.map((control) => ({
        ...control,
        frameworkId: framework.id,
        frameworkShortName: framework.shortName,
      })),
    );
    const q = search.trim().toLowerCase();
    return flat.filter(
      (control) =>
        (frameworkId === "all" || control.frameworkId === frameworkId) &&
        (status === "all" || control.status === status) &&
        (!q || control.code.toLowerCase().includes(q) || control.title.toLowerCase().includes(q)),
    );
  }, [coverage, frameworkId, status, search]);

  return (
    <>
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative w-full max-w-xs">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
            strokeWidth={1.75}
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search controls…"
            className="h-9 w-full rounded-lg border border-hairline bg-surface/60 pl-9 pr-3 text-sm text-foreground outline-none focus:border-hairline-strong"
          />
        </div>
        <select
          value={frameworkId}
          onChange={(e) => setFrameworkId(e.target.value)}
          className="h-9 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary outline-none focus:border-hairline-strong"
        >
          <option value="all">All frameworks</option>
          {coverage.frameworks.map((f) => (
            <option key={f.id} value={f.id}>
              {f.shortName}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as StatusFilter)}
          className="h-9 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary outline-none focus:border-hairline-strong"
        >
          <option value="all">All statuses</option>
          <option value="covered">Covered</option>
          <option value="gap">Gaps</option>
        </select>
        <span className="text-2xs text-foreground-muted sm:ml-auto">{rows.length} controls</span>
      </div>

      <Card flush>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-2xs uppercase tracking-wider text-foreground-muted">
                <th className="px-5 py-2.5 font-medium">Control</th>
                <th className="px-3 py-2.5 font-medium">Framework</th>
                <th className="px-3 py-2.5 font-medium">Status</th>
                <th className="px-3 py-2.5 font-medium">Evidence</th>
                <th className="px-5 py-2.5 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {rows.map((control) => (
                <tr
                  key={control.id}
                  className="border-b border-hairline last:border-0 hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3">
                    <p className="font-medium text-foreground">
                      <span className="font-mono text-foreground-secondary">{control.code}</span> ·{" "}
                      {control.title}
                    </p>
                  </td>
                  <td className="px-3 py-3 text-foreground-secondary">
                    {control.frameworkShortName}
                  </td>
                  <td className="px-3 py-3">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs font-medium",
                        control.status === "covered"
                          ? "bg-success-soft text-success"
                          : "bg-white/[0.05] text-foreground-muted",
                      )}
                    >
                      {control.status === "covered" ? (
                        <CheckCircle2 className="h-3 w-3" strokeWidth={2} />
                      ) : (
                        <CircleDashed className="h-3 w-3" strokeWidth={2} />
                      )}
                      {control.status === "covered" ? "Covered" : "Gap"}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-foreground-secondary">{control.evidenceCount}</td>
                  <td className="px-5 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => setActiveControl(control.id)}
                      className="rounded-md border border-hairline bg-surface/60 px-2 py-1 text-2xs font-medium text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
                    >
                      Evidence
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {activeControl && (
        <ControlEvidenceModal controlId={activeControl} onClose={() => setActiveControl(null)} />
      )}
    </>
  );
}

function ControlEvidenceModal({ controlId, onClose }: { controlId: string; onClose: () => void }) {
  const control = getControl(controlId);
  const { data: evidence, isLoading } = useEvidence({ controlId });

  return (
    <Modal
      open
      onClose={onClose}
      title={control ? `${control.code} · ${control.title}` : "Control evidence"}
      description={control?.frameworkShortName}
    >
      {isLoading ? (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-foreground-muted">
          <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
          Loading…
        </div>
      ) : !evidence || evidence.length === 0 ? (
        <div className="py-8 text-center">
          <p className="text-sm font-medium text-foreground">No evidence linked</p>
          <p className="mt-1 text-xs text-foreground-muted">
            This control is a coverage gap. Link evidence from the{" "}
            <Link href="/evidence" className="text-accent-foreground hover:underline">
              Evidence
            </Link>{" "}
            module.
          </p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {evidence.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-2.5 rounded-lg border border-hairline bg-surface/40 px-3 py-2"
            >
              <FileText className="h-4 w-4 shrink-0 text-foreground-secondary" strokeWidth={1.75} />
              <span className="min-w-0 flex-1 truncate text-sm text-foreground">{item.title}</span>
              {item.currentVersion && (
                <a
                  href={`/api/evidence/${item.id}/versions/current/content?download`}
                  className="text-2xs text-accent-foreground hover:underline"
                >
                  Download
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
