/** Browser-side reports API client. */

import type { Report, ReportKind } from "./types";

export async function fetchReport(kind: ReportKind): Promise<Report> {
  const response = await fetch(`/api/reports/${kind}`, { cache: "no-store" });
  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(data.error ?? `Request failed (${response.status}).`);
  }
  return ((await response.json()) as { report: Report }).report;
}

export function reportExportUrl(kind: ReportKind, format: "pdf" | "xlsx"): string {
  return `/api/reports/${kind}/export?format=${format}`;
}
