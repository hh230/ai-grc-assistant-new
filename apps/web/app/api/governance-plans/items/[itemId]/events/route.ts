import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getPlanItemEvents } from "@/lib/planExecution/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ itemId: string }>;
}

/** The audit trail for one item, in the order it actually happened (Phase 3 hardening) — what a
 * reviewer opens to confirm a completion has (or doesn't have) a matching event. */
export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { itemId } = await params;
    const items = await getPlanItemEvents(actor, itemId);
    return NextResponse.json({ items });
  } catch (error) {
    return errorResponse(error);
  }
}
