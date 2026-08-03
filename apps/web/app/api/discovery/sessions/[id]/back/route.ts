import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { goBackDiscoveryAnswer } from "@/lib/discovery/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * The most recently answered, still-relevant question — pre-filled with its previous answer so
 * the user can edit it. A question a later edit made irrelevant is quietly never offered here
 * (ADR 0066: "quietly reroute, never confuse the user").
 */
export async function POST(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const target = await goBackDiscoveryAnswer(actor, id);
    return NextResponse.json(target);
  } catch (error) {
    return errorResponse(error);
  }
}
