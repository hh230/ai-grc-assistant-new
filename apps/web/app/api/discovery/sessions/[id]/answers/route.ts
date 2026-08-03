import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { submitDiscoveryAnswer } from "@/lib/discovery/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * Submits one answer and returns the next question — or, once the interview concludes, a status
 * with no question. The response never carries signals/frameworks/plan data (ADR 0066): that is
 * a hard contract of the upstream API, not an incidental shape.
 */
export async function POST(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const body = (await request.json().catch(() => null)) as
      | { questionId?: string; value?: unknown }
      | null;
    if (!body?.questionId) {
      throw new ValidationError("questionId is required.");
    }
    const turn = await submitDiscoveryAnswer(actor, id, body.questionId, body.value);
    return NextResponse.json(turn);
  } catch (error) {
    return errorResponse(error);
  }
}
