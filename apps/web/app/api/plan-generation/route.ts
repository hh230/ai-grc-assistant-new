import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { startPlanGeneration } from "@/lib/planGeneration/service";

export const runtime = "nodejs";

/** Creates and runs the `generate_governance_plan` Mission for a just-concluded Discovery
 * session, returning the Report as soon as it pauses at the approval gate (ADR 0066 §3). */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const body = (await request.json().catch(() => null)) as { sessionId?: string } | null;
    if (!body?.sessionId) {
      throw new ValidationError("sessionId is required.");
    }
    const result = await startPlanGeneration(actor, body.sessionId);
    return NextResponse.json(result);
  } catch (error) {
    return errorResponse(error);
  }
}
