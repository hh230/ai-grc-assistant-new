import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { listObligations } from "@/lib/policyIntelligence/service";

export const runtime = "nodejs";

/** Confirmed regulatory obligations (Policy Hunter), proxied from apps/api. */
export async function GET(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const controlDomain = new URL(request.url).searchParams.get("controlDomain") ?? undefined;
    const obligations = await listObligations(actor, controlDomain);
    return NextResponse.json({ obligations });
  } catch (error) {
    return errorResponse(error);
  }
}
