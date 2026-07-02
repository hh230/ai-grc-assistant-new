import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { listAnalyses } from "@/lib/analysis/service";

export const runtime = "nodejs";

/** Latest version per document — the analysis history list. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const analyses = await listAnalyses(actor);
    return NextResponse.json({ analyses });
  } catch (error) {
    return errorResponse(error);
  }
}
