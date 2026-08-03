import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { attachPlanItemEvidence } from "@/lib/planExecution/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ itemId: string }>;
}

/** Always additive and optional (ADR 0066 §5.4) — never a gate on completion. */
export async function POST(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { itemId } = await params;
    const body = (await request.json().catch(() => null)) as { evidenceIds?: unknown } | null;
    if (!Array.isArray(body?.evidenceIds) || body.evidenceIds.some((id) => typeof id !== "string")) {
      throw new ValidationError("evidenceIds must be an array of strings.");
    }
    const item = await attachPlanItemEvidence(actor, itemId, body.evidenceIds as string[]);
    return NextResponse.json(item);
  } catch (error) {
    return errorResponse(error);
  }
}
