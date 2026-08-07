import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { setActiveRelease } from "@/lib/knowledge/service";
import { requireKnowledgeApprover } from "../../../_guard";

export const runtime = "nodejs";

/** Sets which release the industry serves. Rollback is this same call with an older release id —
 * no release is demoted to undo a mistake. */
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ industrySlug: string }> },
): Promise<NextResponse> {
  try {
    const actor = await requireKnowledgeApprover();
    if (!actor) return unauthorized();
    const { industrySlug } = await params;
    const body = (await request.json().catch(() => null)) as {
      releaseId?: string;
      reason?: string;
    } | null;
    if (!body?.releaseId) throw new ValidationError("releaseId is required.");
    return NextResponse.json(
      await setActiveRelease(actor, industrySlug, body.releaseId, body.reason ?? ""),
    );
  } catch (error) {
    return errorResponse(error);
  }
}
