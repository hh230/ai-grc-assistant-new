import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { findOpenSectorInterview, interviewLanguage } from "@/lib/sectorInterview/service";

export const runtime = "nodejs";

/** What this customer left unfinished, if anything — the read that makes the sector stage
 * survivable across a closed tab. */
export async function GET(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const language = interviewLanguage(
      new URL(request.url).searchParams.get("language") ?? undefined,
    );
    return NextResponse.json(await findOpenSectorInterview(actor, language));
  } catch (error) {
    return errorResponse(error);
  }
}
