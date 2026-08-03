import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getPlan } from "@/lib/planExecution/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ planId: string }>;
}

/** One specific plan version (active or superseded) with its items — how the user inspects a
 * past version from the lineage view (ADR 0066 §3.1). */
export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { planId } = await params;
    const detail = await getPlan(actor, planId);
    return NextResponse.json(detail);
  } catch (error) {
    return errorResponse(error);
  }
}
