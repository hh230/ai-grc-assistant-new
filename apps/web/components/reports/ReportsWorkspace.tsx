"use client";

import { useState } from "react";
import {
  BarChart3,
  FileDown,
  FileSpreadsheet,
  FileText,
  Loader2,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { useReport } from "@/hooks/useReport";
import { reportExportUrl } from "@/lib/reports/client";
import { REPORT_KINDS, REPORT_META, type ReportKind } from "@/lib/reports/types";
import { cn } from "@/lib/utils";

const ICON: Record<ReportKind, typeof BarChart3> = {
  executive: BarChart3,
  compliance: ShieldCheck,
  risk: TriangleAlert,
};

export function ReportsWorkspace() {
  const [kind, setKind] = useState<ReportKind>("executive");
  const { data: report, isLoading, isError, error } = useReport(kind);

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        {REPORT_KINDS.map((k) => {
          const Icon = ICON[k];
          const active = k === kind;
          return (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={cn(
                "rounded-2xl border p-4 text-start transition-colors duration-150",
                active
                  ? "border-hairline-strong bg-surface-2"
                  : "border-hairline bg-surface hover:border-hairline-strong",
              )}
            >
              <span
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-lg border",
                  active ? "border-accent/40 bg-accent-soft" : "border-hairline bg-surface-2",
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4",
                    active ? "text-accent-foreground" : "text-foreground-secondary",
                  )}
                  strokeWidth={1.75}
                />
              </span>
              <p className="mt-3 text-sm font-semibold text-foreground">{REPORT_META[k].title}</p>
              <p className="mt-0.5 text-xs text-foreground-muted">{REPORT_META[k].description}</p>
            </button>
          );
        })}
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">
              {REPORT_META[kind].title}
            </h2>
            <p className="text-xs text-foreground-muted">{REPORT_META[kind].subtitle}</p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={reportExportUrl(kind, "pdf")}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
            >
              <FileDown className="h-4 w-4" strokeWidth={1.75} />
              Export PDF
            </a>
            <a
              href={reportExportUrl(kind, "xlsx")}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98]"
            >
              <FileSpreadsheet className="h-4 w-4" strokeWidth={1.75} />
              Export Excel
            </a>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-foreground-muted">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
            Building report…
          </div>
        ) : isError ? (
          <p className="py-10 text-center text-sm text-danger">{(error as Error).message}</p>
        ) : report ? (
          <div className="mt-5 space-y-6">
            {/* KPIs */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {report.kpis.map((kpi) => (
                <div
                  key={kpi.label}
                  className="rounded-lg border border-hairline bg-surface/40 px-3 py-2.5"
                >
                  <p className="text-xl font-semibold tracking-tight text-accent-foreground">
                    {kpi.value}
                  </p>
                  <p className="mt-0.5 text-2xs uppercase tracking-wide text-foreground-muted">
                    {kpi.label}
                  </p>
                </div>
              ))}
            </div>

            {/* Sections */}
            {report.sections.map((section) => (
              <div key={section.heading}>
                <div className="mb-2 flex items-center gap-2">
                  <FileText className="h-3.5 w-3.5 text-foreground-muted" strokeWidth={1.75} />
                  <h3 className="text-sm font-semibold text-foreground">{section.heading}</h3>
                </div>
                {section.narrative && (
                  <p className="mb-2 text-xs text-foreground-muted">{section.narrative}</p>
                )}
                {section.table && (
                  <div className="overflow-x-auto rounded-xl border border-hairline">
                    <table className="w-full min-w-[520px] text-sm">
                      <thead>
                        <tr className="border-b border-hairline bg-white/[0.02] text-start text-2xs uppercase tracking-wider text-foreground-muted">
                          {section.table.columns.map((col) => (
                            <th key={col} className="px-4 py-2 font-medium">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {section.table.rows.length === 0 ? (
                          <tr>
                            <td
                              colSpan={section.table.columns.length}
                              className="px-4 py-4 text-center text-xs text-foreground-muted"
                            >
                              No rows.
                            </td>
                          </tr>
                        ) : (
                          section.table.rows.map((row, r) => (
                            <tr key={r} className="border-b border-hairline last:border-0">
                              {row.map((cell, c) => (
                                <td key={c} className="px-4 py-2 text-foreground-secondary">
                                  {cell}
                                </td>
                              ))}
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
