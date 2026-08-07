import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { getSession } from "@/lib/auth/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { computeCoverage } from "@/lib/governance/coverage";
import { getProgramStatus } from "@/lib/planExecution/programStatus";
import { renderGovernanceStatusReportPdf } from "@/lib/planExecution/statusReport";

export const runtime = "nodejs";

/**
 * Downloads the Governance Status Report — the governance program's own export.
 *
 * Deliberately a separate route from the Home Dashboard's export, not a replacement for it: the
 * two describe different things, and collapsing them would be exactly the conflation the program
 * experience was scoped away from. This one carries no figure derived from document analysis.
 *
 * No date range. A governance program has a version and an assessment date; a rolling window is a
 * question about documents, not about a program.
 */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    const session = await getSession();
    if (!actor || !session) return unauthorized();

    const [status, coverage] = await Promise.all([
      getProgramStatus(actor),
      computeCoverage(actor),
    ]);

    const bytes = await renderGovernanceStatusReportPdf({
      organizationName: session.organizationName,
      generatedBy: actor.userName,
      status,
      coverage,
    });

    const fileName = `governance-status-${new Date().toISOString().slice(0, 10)}.pdf`;
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
