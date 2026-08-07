import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { getSession } from "@/lib/auth/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { computeCoverage } from "@/lib/governance/coverage";
import { getProgramStatus } from "@/lib/dashboard/programStatus";
import { renderGovernanceStatusReportPdf } from "@/lib/dashboard/governanceStatusReport";

export const runtime = "nodejs";

/**
 * Downloads the Governance Status Report.
 *
 * The route is unchanged so an existing bookmark keeps working; what it returns is not. The old
 * export led with a compliance score averaged from AI readings of uploaded documents, in a
 * document a customer may hand to an auditor. It now reports the governance program itself
 * (CLAUDE.md §3 pillar 10).
 *
 * The date-range parameter is gone: a governance program has a version and an assessment date, not
 * a rolling window. Any `?range=` a bookmark still carries is simply ignored.
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

    const pdf = await renderGovernanceStatusReportPdf({
      organizationName: session.organizationName,
      generatedBy: session.name,
      status,
      coverage,
    });

    const filename = `governance-status-${new Date().toISOString().slice(0, 10)}.pdf`;
    return new NextResponse(new Uint8Array(pdf), {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Cache-Control": "no-store",
      },
    }) as NextResponse;
  } catch (error) {
    return errorResponse(error);
  }
}
