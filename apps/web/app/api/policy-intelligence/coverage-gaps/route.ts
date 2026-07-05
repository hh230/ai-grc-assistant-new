import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { scanCoverageGaps } from "@/lib/policyIntelligence/service";

export const runtime = "nodejs";

/** This tenant's regulatory coverage-gap scan (Policy Hunter), proxied from apps/api. */
export async function GET(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const controlDomain = new URL(request.url).searchParams.get("controlDomain") ?? undefined;
    const scan = await scanCoverageGaps(actor, controlDomain);
    return NextResponse.json(scan);
  } catch (error) {
    return errorResponse(error);
  }
}
