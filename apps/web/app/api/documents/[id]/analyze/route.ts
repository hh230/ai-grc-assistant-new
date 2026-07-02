import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { startAnalysis } from "@/lib/analysis/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Kick off the analysis pipeline for a document (returns immediately; poll for status). */
export async function POST(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const record = await startAnalysis(actor, id);
    return NextResponse.json({ analysis: record }, { status: 202 });
  } catch (error) {
    return errorResponse(error);
  }
}
