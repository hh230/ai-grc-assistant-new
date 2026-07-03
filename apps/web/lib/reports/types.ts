/**
 * Report data model — a renderer-agnostic structure the on-screen preview, the PDF writer,
 * and the Excel writer all consume. A report is a set of headline KPIs plus sections, each
 * of which may carry KPIs, a narrative, and/or a table.
 */

export const REPORT_KINDS = ["executive", "compliance", "risk"] as const;
export type ReportKind = (typeof REPORT_KINDS)[number];

export interface ReportKpi {
  label: string;
  value: string;
}

export interface ReportTable {
  title: string;
  columns: string[];
  rows: string[][];
}

export interface ReportSection {
  heading: string;
  narrative?: string;
  kpis?: ReportKpi[];
  table?: ReportTable;
}

export interface Report {
  kind: ReportKind;
  title: string;
  subtitle: string;
  tenantName: string;
  generatedAt: string;
  generatedBy: string;
  kpis: ReportKpi[];
  sections: ReportSection[];
}
