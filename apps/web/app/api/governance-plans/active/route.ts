import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getActivePlan } from "@/lib/planExecution/service";

export const runtime = "nodejs";

/** The tenant's currently active Governance Plan (ADR 0066 §3.1) with its items, or `null` if
 * none has been finalized yet. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const detail = await getActivePlan(actor);
    return NextResponse.json(detail);
  } catch (error) {
    return errorResponse(error);
  }
}
