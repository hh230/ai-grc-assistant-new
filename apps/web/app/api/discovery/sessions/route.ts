import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { startDiscoverySession } from "@/lib/discovery/service";

export const runtime = "nodejs";

/** Starts a new adaptive-interview Discovery Session for the signed-in user's organization. */
export async function POST(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const turn = await startDiscoverySession(actor);
    return NextResponse.json(turn, { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}
