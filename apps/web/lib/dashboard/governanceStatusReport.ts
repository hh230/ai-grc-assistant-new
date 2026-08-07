/**
 * The Governance Status Report — the PDF a customer takes to a board or an auditor.
 *
 * Replaces the old dashboard export, which led with a compliance score averaged from AI readings
 * of uploaded documents. That number described the uploads, not the organization, and it was the
 * headline of an audit-facing artifact (CLAUDE.md §3 pillar 10). The PDF was never the problem —
 * its contents were.
 *
 * Five sections, and every figure traceable to the governance program rather than to a document:
 *
 *     governance maturity   where the organization stands, per dimension
 *     program execution     what the plan committed to, and what is done
 *     evidence coverage     what can actually be proved today
 *     top risks             the gaps the assessment found
 *     next actions          what to do, in the plan's own order
 *
 * **No average derived from document analysis appears anywhere in it**, and none may be added: the
 * input type has no field that could carry one.
 */

import { PDFDocument, StandardFonts, rgb, type PDFFont, type PDFPage } from "pdf-lib";
import type { CoverageReport, FrameworkCoverage } from "@/lib/governance/coverage";
import type { PlanDetail } from "@/lib/planExecution/types";
import { MATURITY_DIMENSION_ORDER } from "@/lib/planExecution/types";
import { PRIORITY_RANK } from "@/lib/planExecution/grouping";
import type { ProgramStatus } from "./programStatus";

const PAGE_W = 595.28;
const PAGE_H = 841.89;
const MARGIN = 50;
const HEADER_H = 34;
const FOOTER_H = 24;
const CONTENT_W = PAGE_W - MARGIN * 2;
const CONTENT_TOP = PAGE_H - MARGIN - HEADER_H;
const CONTENT_BOTTOM = MARGIN + FOOTER_H;

const INK = rgb(0.09, 0.09, 0.11);
const BODY = rgb(0.2, 0.2, 0.24);
const MUTED = rgb(0.45, 0.45, 0.5);
const ACCENT = rgb(0.43, 0.42, 0.87);
const LINE = rgb(0.85, 0.85, 0.88);
const HEADER_BG = rgb(0.96, 0.96, 0.98);

/**
 * pdf-lib's standard Helvetica font only supports WinAnsi (Windows-1252) encoding — it
 * throws on any other code point. Dynamic content here (organization names, AI-derived gap/
 * recommendation text) can be Arabic (this app generates Arabic-language analyses), which
 * would otherwise crash the export. Strip anything outside the WinAnsi-safe range rather
 * than fail the whole report; the PDF stays English-only, matching the same constraint
 * already documented for the P9 reports export (lib/reports/pdf.ts).
 */
function sanitizeForPdf(value: string): string {
  return String(value ?? "")
    .replace(/[^\x20-\x7E\xA0-\xFF]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * pdf-lib's Helvetica is WinAnsi-only, so Arabic text survives sanitisation as stray punctuation.
 * An entry with almost no Latin letters left is dropped rather than rendered as a meaningless row —
 * the same rule the reports export already follows.
 */
const NON_ENGLISH_NOTE =
  "Some items written in Arabic are omitted from this English-only export — view them in the app.";

function hasEnglishText(value: string): boolean {
  return (sanitizeForPdf(value).match(/[A-Za-z]/g) ?? []).length >= 5;
}

const DIMENSION_LABEL: Record<string, string> = {
  governance: "Governance",
  risk: "Risk Management",
  compliance: "Compliance",
  cyber: "Cyber Security",
  leadership: "Leadership & Accountability",
};

export interface GovernanceStatusReportInput {
  organizationName: string;
  generatedBy: string;
  status: ProgramStatus;
  coverage: CoverageReport;
}

export async function renderGovernanceStatusReportPdf(
  input: GovernanceStatusReportInput,
): Promise<Buffer> {
  const { organizationName, generatedBy, status, coverage } = input;
  const plan: PlanDetail | null = status.plan;
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const bold = await doc.embedFont(StandardFonts.HelveticaBold);

  let page = doc.addPage([PAGE_W, PAGE_H]);
  let y = CONTENT_TOP;

  const newPage = () => {
    page = doc.addPage([PAGE_W, PAGE_H]);
    y = CONTENT_TOP;
  };
  const ensure = (needed: number) => {
    if (y - needed < CONTENT_BOTTOM) newPage();
  };
  const truncate = (value: string, f: PDFFont, size: number, maxW: number): string => {
    let t = String(value ?? "");
    if (f.widthOfTextAtSize(t, size) <= maxW) return t;
    while (t.length > 1 && f.widthOfTextAtSize(`${t}…`, size) > maxW) t = t.slice(0, -1);
    return `${t}…`;
  };
  const wrap = (value: string, f: PDFFont, size: number, maxW: number): string[] => {
    const words = String(value ?? "").split(/\s+/).filter(Boolean);
    const lines: string[] = [];
    let current = "";
    for (const word of words) {
      const candidate = current ? `${current} ${word}` : word;
      if (f.widthOfTextAtSize(candidate, size) > maxW && current) {
        lines.push(current);
        current = word;
      } else {
        current = candidate;
      }
    }
    if (current) lines.push(current);
    return lines;
  };
  const line = (yy: number) => {
    page.drawLine({
      start: { x: MARGIN, y: yy },
      end: { x: PAGE_W - MARGIN, y: yy },
      thickness: 0.5,
      color: LINE,
    });
  };
  const write = (value: string, x: number, size: number, f: PDFFont, color = INK) => {
    page.drawText(sanitizeForPdf(value), { x, y, size, font: f, color });
  };

  const heading = (text: string) => {
    ensure(30);
    write(text, MARGIN, 12.5, bold);
    y -= 17;
  };
  const narrative = (text: string) => {
    for (const l of wrap(text, font, 9.5, CONTENT_W)) {
      ensure(14);
      write(l, MARGIN, 9.5, font, BODY);
      y -= 13;
    }
    y -= 6;
  };
  const tableContext = () => ({
    page: () => page,
    y: () => y,
    setY: (v: number) => (y = v),
    ensure,
    truncate,
    font,
    bold,
    line,
    newPage,
  });

  write("Governance Status Report", MARGIN, 19, bold);
  y -= 20;
  write(`Organization: ${organizationName}`, MARGIN, 10, font, MUTED);
  y -= 14;
  write(`Generated ${new Date().toUTCString()}   ·   by ${generatedBy}`, MARGIN, 9, font, MUTED);
  y -= 16;
  line(y);
  y -= 22;

  if (plan === null) {
    narrative(
      "This organization has no governance program yet. Run the governance assessment to produce " +
        "a plan; this report describes that program and has nothing to describe until one exists.",
    );
    const empty = await doc.save();
    return Buffer.from(empty);
  }

  const remaining = plan.items.filter((item) => item.status !== "done");
  const completed = plan.items.length - remaining.length;

  // Program standing — the same three facts the home page opens with, in the same order.
  const facts = [
    { label: "PLAN VERSION", value: `v${plan.plan.version}` },
    {
      label: "ASSESSED",
      value: status.assessedAt ? status.assessedAt.slice(0, 10) : "—",
    },
    {
      label: "NEXT REVIEW",
      value: status.reviewDueAt ? status.reviewDueAt.slice(0, 10) : "—",
    },
    { label: "STATUS", value: status.state === "reviewDue" ? "Review due" : "Active" },
  ];
  const perRow = 4;
  const kpiW = CONTENT_W / perRow;
  ensure(46);
  facts.forEach((fact, col) => {
    const x = MARGIN + col * kpiW;
    page.drawText(sanitizeForPdf(fact.value), { x, y, size: 15, font: bold, color: ACCENT });
    page.drawText(sanitizeForPdf(fact.label), { x, y: y - 13, size: 7.5, font, color: MUTED });
  });
  y -= 44;

  heading("Governance maturity");
  drawTable(
    { columns: ["Dimension", "Rating", "Level"], colWeights: [0.45, 0.2, 0.35] },
    MATURITY_DIMENSION_ORDER.flatMap((d) => {
      const rating = plan.plan.maturityBaseline[d];
      return rating ? [[DIMENSION_LABEL[d] ?? d, `${rating.stars} of 5`, rating.label]] : [];
    }),
    tableContext(),
  );
  y -= 10;

  heading("Program execution");
  narrative(
    `${completed} of ${plan.items.length} actions completed. ` +
      `${remaining.length} remaining in plan v${plan.plan.version}.`,
  );

  heading("Evidence coverage");
  narrative(
    `${coverage.overall.coveredControls} of ${coverage.overall.totalControls} controls have ` +
      `evidence linked, across ${coverage.frameworks.length} frameworks. ` +
      `${coverage.overall.gaps} controls have none.`,
  );
  drawTable(
    { columns: ["Framework", "Controls", "Covered", "Coverage"], colWeights: [0.4, 0.2, 0.2, 0.2] },
    coverage.frameworks.map((f: FrameworkCoverage) => [
      f.shortName,
      String(f.total),
      String(f.covered),
      `${f.coveragePct}%`,
    ]),
    tableContext(),
  );
  y -= 10;

  // The assessment's own top risks — not the risk register, which is a different discipline with
  // its own report. These are the gaps that produced this plan.
  heading("Top risks");
  const risks = plan.plan.topRisks.filter((risk) => hasEnglishText(String(risk.description ?? "")));
  if (risks.length === 0) {
    narrative(
      plan.plan.topRisks.length === 0
        ? "No risks were flagged by the assessment behind this plan."
        : NON_ENGLISH_NOTE,
    );
  } else {
    drawTable(
      { columns: ["Risk", "Severity", "Business impact"], colWeights: [0.42, 0.14, 0.44] },
      risks.map((risk) => [
        String(risk.description ?? "—"),
        String(risk.severity ?? "—"),
        String(risk.impact ?? "—"),
      ]),
      tableContext(),
    );
    if (risks.length < plan.plan.topRisks.length) narrative(NON_ENGLISH_NOTE);
  }
  y -= 10;

  heading("Next actions");
  const nextActions = [...remaining]
    .sort((a, b) => {
      const byPriority = PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
      if (byPriority !== 0) return byPriority;
      return (a.dueAt ?? Infinity) - (b.dueAt ?? Infinity);
    })
    .filter((item) => hasEnglishText(item.title));
  if (nextActions.length === 0) {
    narrative(
      remaining.length === 0
        ? "Every action in this plan is complete."
        : NON_ENGLISH_NOTE,
    );
  } else {
    drawTable(
      { columns: ["Action", "Priority", "Due"], colWeights: [0.56, 0.2, 0.24] },
      nextActions.map((item) => [
        item.title,
        item.priority,
        item.dueAt ? new Date(item.dueAt * 1000).toISOString().slice(0, 10) : "—",
      ]),
      tableContext(),
    );
  }

  const safeOrganizationName = sanitizeForPdf(organizationName) || "Organization";
  const pages = doc.getPages();
  pages.forEach((p, i) => {
    stampHeader(p, bold, font, safeOrganizationName, i > 0);
    stampFooter(p, font, i + 1, pages.length);
  });

  const bytes = await doc.save();
  return Buffer.from(bytes);
}

function stampHeader(
  page: PDFPage,
  bold: PDFFont,
  font: PDFFont,
  organizationName: string,
  isContinuationPage: boolean,
) {
  const y = PAGE_H - MARGIN + 4;
  if (isContinuationPage) {
    page.drawText("Governance, Risk & Compliance Summary", {
      x: MARGIN,
      y,
      size: 9,
      font: bold,
      color: MUTED,
    });
  }
  page.drawText(organizationName, {
    x: PAGE_W - MARGIN - font.widthOfTextAtSize(organizationName, 9),
    y,
    size: 9,
    font,
    color: MUTED,
  });
  page.drawLine({
    start: { x: MARGIN, y: y - 6 },
    end: { x: PAGE_W - MARGIN, y: y - 6 },
    thickness: 0.5,
    color: LINE,
  });
}

function stampFooter(page: PDFPage, font: PDFFont, pageNumber: number, totalPages: number) {
  const label = `Page ${pageNumber} of ${totalPages}`;
  page.drawText(label, {
    x: (PAGE_W - font.widthOfTextAtSize(label, 8)) / 2,
    y: MARGIN - 12,
    size: 8,
    font,
    color: MUTED,
  });
  const dateLabel = `Generated ${new Date().toISOString().slice(0, 10)}`;
  page.drawText(dateLabel, {
    x: PAGE_W - MARGIN - font.widthOfTextAtSize(dateLabel, 8),
    y: MARGIN - 12,
    size: 8,
    font,
    color: MUTED,
  });
}

interface TableContext {
  page: () => PDFPage;
  y: () => number;
  setY: (value: number) => void;
  ensure: (needed: number) => void;
  truncate: (value: string, f: PDFFont, size: number, maxW: number) => string;
  font: PDFFont;
  bold: PDFFont;
  line: (yy: number) => void;
  newPage: () => void;
}

function drawTable(
  spec: { columns: string[]; colWeights: number[] },
  rows: string[][],
  ctx: TableContext,
) {
  const rowH = 17;
  const size = 8;
  const colWidths = spec.colWeights.map((w) => w * CONTENT_W);

  const drawRow = (cells: string[], f: PDFFont, header: boolean) => {
    if (ctx.y() - rowH < CONTENT_BOTTOM) ctx.newPage();
    const rowTop = ctx.y();
    const page = ctx.page();
    if (header) {
      page.drawRectangle({
        x: MARGIN,
        y: rowTop - rowH + 4,
        width: CONTENT_W,
        height: rowH,
        color: HEADER_BG,
      });
    }
    let x = MARGIN;
    cells.forEach((cell, i) => {
      const w = colWidths[i] ?? CONTENT_W / cells.length;
      page.drawText(ctx.truncate(sanitizeForPdf(String(cell ?? "")), f, size, w - 8), {
        x: x + 4,
        y: rowTop - 12,
        size,
        font: f,
        color: header ? INK : BODY,
      });
      x += w;
    });
    ctx.line(rowTop - rowH + 3);
    ctx.setY(rowTop - rowH);
  };

  drawRow(spec.columns, ctx.bold, true);
  for (const row of rows) drawRow(row, ctx.font, false);
}
