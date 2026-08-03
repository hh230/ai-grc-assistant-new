import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { startPlanItem } from "@/lib/planExecution/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ itemId: string }>;
}

/** Not started -> in progress (Phase 4). Idempotent from `not_started` only. */
export async function POST(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { itemId } = await params;
    const item = await startPlanItem(actor, itemId);
    return NextResponse.json(item);
  } catch (error) {
    return errorResponse(error);
  }
}
