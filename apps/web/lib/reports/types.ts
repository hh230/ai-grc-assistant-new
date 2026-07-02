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

export const REPORT_META: Record<
  ReportKind,
  { title: string; subtitle: string; description: string }
> = {
  executive: {
    title: "Executive GRC Report",
    subtitle: "Governance, risk & compliance posture at a glance",
    description:
      "A leadership summary of compliance coverage, risk exposure, and control evidence.",
  },
  compliance: {
    title: "Compliance Report",
    subtitle: "Framework coverage and control assurance",
    description:
      "Per-framework control coverage, gaps, and the policies and evidence that support them.",
  },
  risk: {
    title: "Risk Report",
    subtitle: "Risk register, scoring, and treatment",
    description:
      "The full risk register with severity distribution, status, and acceptance decisions.",
  },
};
