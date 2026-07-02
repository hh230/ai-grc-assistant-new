import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { buildReport } from "@/lib/reports/service";
import { renderReportPdf } from "@/lib/reports/pdf";
import { renderReportXlsx } from "@/lib/reports/xlsx";
import { REPORT_KINDS, type ReportKind } from "@/lib/reports/types";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ kind: string }>;
}

const CONTENT_TYPE: Record<"pdf" | "xlsx", string> = {
  pdf: "application/pdf",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

/** Export a report as a downloadable PDF or Excel file. */
export async function GET(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { kind } = await params;
    if (!(REPORT_KINDS as readonly string[]).includes(kind)) {
      throw new ValidationError("Unknown report type.");
    }
    const format = new URL(request.url).searchParams.get("format") === "xlsx" ? "xlsx" : "pdf";

    const report = await buildReport(actor, kind as ReportKind);
    const bytes = format === "pdf" ? await renderReportPdf(report) : await renderReportXlsx(report);
    const date = new Date().toISOString().slice(0, 10);
    const fileName = `${kind}-report-${date}.${format}`;

    return new NextResponse(new Uint8Array(bytes), {
      status: 200,
      headers: {
        "Content-Type": CONTENT_TYPE[format],
        "Content-Length": String(bytes.length),
        "Content-Disposition": `attachment; filename="${fileName}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return errorResponse(error);
  }
}
