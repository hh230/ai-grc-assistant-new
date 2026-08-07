import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { actOnRelease } from "@/lib/knowledge/service";
import type { ReleaseAction } from "@/lib/knowledge/types";
import { requireKnowledgeApprover } from "../../../_guard";

export const runtime = "nodejs";

const ACTIONS: readonly ReleaseAction[] = ["submit", "approve", "reject", "publish"];

/** The four lifecycle transitions. The action is validated against a closed set here rather than
 * forwarded — a path segment is caller input, and forwarding it would let any string become a URL
 * on the backend. */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ releaseId: string; action: string }> },
): Promise<NextResponse> {
  try {
    const actor = await requireKnowledgeApprover();
    if (!actor) return unauthorized();
    const { releaseId, action } = await params;
    if (!ACTIONS.includes(action as ReleaseAction)) {
      throw new ValidationError(`Unknown action '${action}'.`);
    }
    return NextResponse.json(await actOnRelease(actor, releaseId, action as ReleaseAction));
  } catch (error) {
    return errorResponse(error);
  }
}
