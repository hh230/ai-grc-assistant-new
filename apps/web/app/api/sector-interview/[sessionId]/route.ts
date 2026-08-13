import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { interviewLanguage, openSectorInterview } from "@/lib/sectorInterview/service";

export const runtime = "nodejs";

/** Opens or resumes this session's sector stage — the point where what a reviewer activated
 * becomes what this organization is asked. */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { sessionId } = await params;
    // The language is presentation only: it selects which published translation is folded in, and
    // never which questions are asked or how an answer is stored.
    const language = interviewLanguage(
      new URL(request.url).searchParams.get("language") ?? undefined,
    );
    // The organization is the actor's own tenant, never a value the browser supplies — the whole
    // interview is written under it.
    return NextResponse.json(
      await openSectorInterview(actor, sessionId, actor.tenantId, language),
    );
  } catch (error) {
    return errorResponse(error);
  }
}
