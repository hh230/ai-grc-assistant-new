import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { skipDiscoveryQuestion } from "@/lib/discovery/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Skips an optional question (free-text clarifications, supplementary multi-select context). */
export async function POST(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const body = (await request.json().catch(() => null)) as { questionId?: string } | null;
    if (!body?.questionId) {
      throw new ValidationError("questionId is required.");
    }
    const turn = await skipDiscoveryQuestion(actor, id, body.questionId);
    return NextResponse.json(turn);
  } catch (error) {
    return errorResponse(error);
  }
}
