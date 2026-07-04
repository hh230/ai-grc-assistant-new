import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { getSession } from "@/lib/auth/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import {
  getDashboardMetrics,
  parseDashboardRange,
  type DashboardRangeDays,
} from "@/lib/dashboard/metrics";
import { renderDashboardReportPdf } from "@/lib/dashboard/report";

export const runtime = "nodejs";

const RANGE_LABEL: Record<DashboardRangeDays, string> = {
  7: "Last 7 days",
  30: "Last 30 days",
  90: "Last 90 days",
};

/** Downloads a real, data-grounded executive GRC summary for the active organization. */
export async function GET(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    const session = await getSession();
    if (!actor || !session) return unauthorized();

    const rangeDays = parseDashboardRange(
      new URL(request.url).searchParams.get("range") ?? undefined,
    );
    const metrics = await getDashboardMetrics(actor, rangeDays);
    const bytes = await renderDashboardReportPdf({
      organizationName: session.organizationName,
      generatedBy: actor.userName,
      rangeLabel: RANGE_LABEL[rangeDays],
      metrics,
    });

    const date = new Date().toISOString().slice(0, 10);
    const fileName = `grc-dashboard-summary-${date}.pdf`;

    return new NextResponse(new Uint8Array(bytes), {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Length": String(bytes.length),
        "Content-Disposition": `attachment; filename="${fileName}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return errorResponse(error);
  }
}
