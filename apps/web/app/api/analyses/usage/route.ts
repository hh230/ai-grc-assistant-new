import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getAnalysisUsage } from "@/lib/analysis/service";

export const runtime = "nodejs";
// The daily counter is time-sensitive and per-user; never serve it from a shared cache.
export const dynamic = "force-dynamic";

/** The current user's remaining beta analysis budget for today. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const usage = await getAnalysisUsage(actor);
    return NextResponse.json({ usage });
  } catch (error) {
    return errorResponse(error);
  }
}
