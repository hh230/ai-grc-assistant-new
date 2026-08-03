import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { completePlanItem } from "@/lib/planExecution/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ itemId: string }>;
}

/** Evidence is never checked (ADR 0066 §5.4) — completion is the practitioner's own attestation.
 * Idempotent: completing an already-done item is a no-op, not an error. */
export async function POST(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { itemId } = await params;
    const item = await completePlanItem(actor, itemId);
    return NextResponse.json(item);
  } catch (error) {
    return errorResponse(error);
  }
}
