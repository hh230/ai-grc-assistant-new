import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { generateRelease } from "@/lib/knowledge/service";
import { requireKnowledgeApprover } from "../_guard";

export const runtime = "nodejs";

/** Asks the governance model for a sector's questions — once. Every later customer in that sector
 * reads the stored release; no customer request ever reaches a model through this path. */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await requireKnowledgeApprover();
    if (!actor) return unauthorized();
    const body = (await request.json().catch(() => null)) as { industrySlug?: string } | null;
    if (!body?.industrySlug) throw new ValidationError("industrySlug is required.");
    return NextResponse.json(await generateRelease(actor, body.industrySlug));
  } catch (error) {
    return errorResponse(error);
  }
}
