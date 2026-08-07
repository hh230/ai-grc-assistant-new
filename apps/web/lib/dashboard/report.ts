/**
 * Executive dashboard PDF export — a real, data-grounded management report (not a
 * screenshot), built from the same `DashboardMetrics` the on-screen cards render. English
 * only: pdf-lib's standard fonts cannot encode Arabic glyphs (same constraint documented
 * in lib/reports/pdf.ts for the P9 reports export). A4, paginates automatically, and
 * stamps a consistent header/footer (organization + report title, page N of total) on
 * every page — done as a final pass once the total page count is known.
 */

import { PDFDocument, StandardFonts, rgb, type PDFFont, type PDFPage } from "pdf-lib";
import type { DashboardMetrics } from "./metrics";

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

const COMPLIANCE_LABEL: Record<DashboardMetrics["complianceBand"], string> = {
  veryLow: "Very Low",
  medium: "Medium",
  high: "Good",
  none: "No data",
};
const RISK_LABEL: Record<DashboardMetrics["riskBand"], string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  none: "No data",
};

export interface DashboardReportInput {
  organizationName: string;
  generatedBy: string;
  rangeLabel: string;
  metrics: DashboardMetrics;
}

export async function renderDashboardReportPdf(input: DashboardReportInput): Promise<Buffer> {
  const { organizationName, generatedBy, rangeLabel, metrics } = input;
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

  // Title block
  write("Governance, Risk & Compliance Summary", MARGIN, 19, bold);
  y -= 20;
  write(
    `Organization: ${organizationName}   ·   Date range: ${rangeLabel}`,
    MARGIN,
    10,
    font,
    MUTED,
  );
  y -= 14;
  write(`Generated ${new Date().toUTCString()}   ·   by ${generatedBy}`, MARGIN, 9, font, MUTED);
  y -= 16;
  line(y);
  y -= 22;

  // Headline KPIs
  const kpis = [
    { label: "COMPLIANCE LEVEL", value: `${COMPLIANCE_LABEL[metrics.complianceBand]}` },
    {
      label: "COMPLIANCE SCORE",
      value: metrics.complianceScore != null ? `${metrics.complianceScore}/100` : "—",
    },
    { label: "RISK LEVEL", value: `${RISK_LABEL[metrics.riskBand]}` },
    { label: "RISK SCORE", value: metrics.riskScore != null ? `${metrics.riskScore}/100` : "—" },
  ];
  const perRow = 4;
  const kpiW = CONTENT_W / perRow;
  ensure(46);
  kpis.forEach((kpi, col) => {
    const x = MARGIN + col * kpiW;
    page.drawText(sanitizeForPdf(kpi.value), { x, y, size: 15, font: bold, color: ACCENT });
    page.drawText(sanitizeForPdf(kpi.label), { x, y: y - 13, size: 7.5, font, color: MUTED });
  });
  y -= 40;
  ensure(16);
  write(
    `Documents analyzed: ${metrics.documentsAnalyzedCount}   ·   Frameworks used: ${
      metrics.frameworksUsed.length > 0 ? metrics.frameworksUsed.join(", ") : "None yet"
    }`,
    MARGIN,
    9,
    font,
    MUTED,
  );
  y -= 20;

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

  // English-only export (see sanitizeForPdf) — an entry generated from an Arabic-language
  // analysis has nothing but stray digits/punctuation left after stripping non-WinAnsi
  // characters, so it's dropped rather than rendered as a near-meaningless row. Requiring a
  // handful of actual Latin letters (not just length) filters those out reliably.
  const hasEnglishText = (value: string) => (sanitizeForPdf(value).match(/[A-Za-z]/g) ?? []).length >= 5;
  const englishGaps = metrics.topGaps.filter((g) => hasEnglishText(g.description));
  const englishRecommendations = metrics.topRecommendations.filter((r) => hasEnglishText(r.change));
  const nonEnglishNote =
    "Some items from Arabic-language analyses are omitted from this English-only export — view them in the app.";

  // Summary Analysis
  heading("Summary Analysis");
  narrative(buildSummaryNarrative(metrics));

  // Main Findings / Identified Gaps
  heading("Identified Gaps");
  if (englishGaps.length === 0) {
    narrative(
      metrics.topGaps.length === 0
        ? "No gaps identified in analyses from the selected date range."
        : nonEnglishNote,
    );
  } else {
    drawTable(
      { columns: ["Area", "Description", "Framework"], colWeights: [0.22, 0.58, 0.2] },
      englishGaps.map((g) => [g.area, g.description, g.framework ?? "—"]),
      {
        page: () => page,
        y: () => y,
        setY: (v) => (y = v),
        ensure,
        truncate,
        font,
        bold,
        line,
        newPage,
      },
    );
    if (englishGaps.length < metrics.topGaps.length) narrative(nonEnglishNote);
  }
  y -= 10;

  // Key Recommendations
  heading("Key Recommendations");
  if (englishRecommendations.length === 0) {
    narrative(
      metrics.topRecommendations.length === 0
        ? "No high-priority recommendations from analyses in the selected date range."
        : nonEnglishNote,
    );
  } else {
    drawTable(
      { columns: ["Recommendation", "Reason", "Framework"], colWeights: [0.32, 0.48, 0.2] },
      englishRecommendations.map((r) => [r.change, r.reason, r.framework ?? "—"]),
      {
        page: () => page,
        y: () => y,
        setY: (v) => (y = v),
        ensure,
        truncate,
        font,
        bold,
        line,
        newPage,
      },
    );
    if (englishRecommendations.length < metrics.topRecommendations.length) narrative(nonEnglishNote);
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

function buildSummaryNarrative(metrics: DashboardMetrics): string {
  if (metrics.documentsAnalyzedCount === 0) {
    return "No completed analyses were found for this organization in the selected date range. Upload and analyze documents to populate this report.";
  }
  const complianceText =
    metrics.complianceScore != null
      ? `a compliance level of ${COMPLIANCE_LABEL[metrics.complianceBand].toLowerCase()} (${metrics.complianceScore}/100)`
      : "no scored compliance data yet";
  const riskText =
    metrics.riskScore != null
      ? `a risk level of ${RISK_LABEL[metrics.riskBand].toLowerCase()} (${metrics.riskScore}/100)`
      : "no scored risk data yet";
  return (
    `Based on ${metrics.documentsAnalyzedCount} analyzed document(s) in this period, the organization shows ` +
    `${complianceText} and ${riskText}. ${metrics.topGaps.length} gap(s) and ` +
    `${metrics.topRecommendations.length} high-priority recommendation(s) were identified across ` +
    `${metrics.frameworksUsed.length} framework(s) assessed.`
  );
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
