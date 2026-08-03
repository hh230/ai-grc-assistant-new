import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getActiveDiscoverySession } from "@/lib/discovery/service";

export const runtime = "nodejs";

/**
 * The organization's in-progress Discovery Session, if any — how the interview resumes without
 * the client needing to remember a session id (ADR 0066). `null` when there is none.
 */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const turn = await getActiveDiscoverySession(actor);
    return NextResponse.json(turn);
  } catch (error) {
    return errorResponse(error);
  }
}
