import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { findOpenSectorInterview } from "@/lib/sectorInterview/service";

export const runtime = "nodejs";

/** What this customer left unfinished, if anything — the read that makes the sector stage
 * survivable across a closed tab. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    return NextResponse.json(await findOpenSectorInterview(actor));
  } catch (error) {
    return errorResponse(error);
  }
}
