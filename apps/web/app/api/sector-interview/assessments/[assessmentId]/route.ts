import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { completeSectorInterview, recordSectorAnswers } from "@/lib/sectorInterview/service";
import type { SectorAnswer } from "@/lib/sectorInterview/types";

export const runtime = "nodejs";

/**
 * Records the answers and concludes the assessment in one request.
 *
 * One request because the two belong together: an assessment left open holds answers a plan cannot
 * be built from, and a customer who closed the tab between two calls would have neither a finished
 * interview nor a reason to return to it. The backend still writes them as separate, individually
 * guarded operations — this is a single user intent, not a single transaction.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ assessmentId: string }> },
): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { assessmentId } = await params;
    const body = (await request.json().catch(() => null)) as { answers?: SectorAnswer[] } | null;
    if (!body?.answers?.length) throw new ValidationError("answers are required.");
    await recordSectorAnswers(actor, assessmentId, body.answers);
    await completeSectorInterview(actor, assessmentId);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
