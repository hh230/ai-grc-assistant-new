import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { computeCoverage } from "@/lib/governance/coverage";

export const runtime = "nodejs";

/** Control coverage across frameworks, derived from evidence links. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const report = await computeCoverage(actor);
    return NextResponse.json({ coverage: report });
  } catch (error) {
    return errorResponse(error);
  }
}
