import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { reopenPlanItem } from "@/lib/planExecution/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ itemId: string }>;
}

/** Reversible by construction (ADR 0066 §5.3) — un-completing a task needs no undo logic beyond
 * this call; the next maturity read simply reflects it no longer being done. */
export async function POST(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { itemId } = await params;
    const item = await reopenPlanItem(actor, itemId);
    return NextResponse.json(item);
  } catch (error) {
    return errorResponse(error);
  }
}
