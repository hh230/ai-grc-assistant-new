import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ForbiddenError, ValidationError } from "@/lib/errors";
import { approvePlanGeneration, canApprovePlanGeneration } from "@/lib/planGeneration/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ missionId: string }>;
}

/** Crosses the ADR 0044 human-approval gate — the plan is persisted as a new immutable version
 * (ADR 0066 §3.1) the moment this succeeds. Enforced here (not just hidden client-side) and again
 * by grc-api itself, which holds the same rule independently. */
export async function POST(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    if (!canApprovePlanGeneration(actor.roles)) {
      throw new ForbiddenError("Your role cannot approve and activate a governance plan.");
    }
    const { missionId } = await params;
    const body = (await request.json().catch(() => null)) as { decisionId?: string } | null;
    if (!body?.decisionId) {
      throw new ValidationError("decisionId is required.");
    }
    await approvePlanGeneration(actor, missionId, body.decisionId);
    return new NextResponse(null, { status: 204 });
  } catch (error) {
    return errorResponse(error);
  }
}
