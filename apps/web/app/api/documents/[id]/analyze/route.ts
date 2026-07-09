import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { startAnalysis } from "@/lib/analysis/service";

export const runtime = "nodejs";
// The response returns immediately, but the pipeline keeps running in the background via
// `waitUntil` (see analysis/service.ts) — Vercel bounds `waitUntil` work by the invoking
// function's own `maxDuration`, so this must cover the pipeline's real worst case (extract +
// embed + up to two LLM assessment attempts), not just the fast initial response.
export const maxDuration = 300;

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
