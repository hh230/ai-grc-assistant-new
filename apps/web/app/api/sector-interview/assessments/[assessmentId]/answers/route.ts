import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { recordSectorAnswers } from "@/lib/sectorInterview/service";
import type { SectorAnswer } from "@/lib/sectorInterview/types";

export const runtime = "nodejs";

/**
 * Records answers WITHOUT concluding the interview — how an answer is kept the moment it is given.
 *
 * Deliberately not the same route as the final submit one level up. That one records and concludes
 * in a single request because they are one intent; this one must not conclude anything, and a flag
 * on a shared route would be one boolean away from ending an interview at question three.
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
    return NextResponse.json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
