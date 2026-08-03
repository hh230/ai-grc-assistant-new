import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { listMissions } from "@/lib/missions/service";

export const runtime = "nodejs";

/** Lists mission runs for the signed-in user's organization. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();

    const missions = await listMissions(actor);
    return NextResponse.json({ missions });
  } catch (error) {
    return errorResponse(error);
  }
}
