import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getPendingPlanGeneration } from "@/lib/planGeneration/service";

export const runtime = "nodejs";

/** A Mission the actor left mid-review (awaiting approval), if one exists — lets `/discovery`
 * resume straight into the Report instead of restarting the interview. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const result = await getPendingPlanGeneration(actor);
    return NextResponse.json(result);
  } catch (error) {
    return errorResponse(error);
  }
}
