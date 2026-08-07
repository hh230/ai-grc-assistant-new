import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { importAuthoredPack } from "@/lib/knowledge/service";
import { requireKnowledgeApprover } from "../../../_guard";

export const runtime = "nodejs";

/** Imports an authored pack as a draft release. Registering the industry is part of it — the pack
 * file declares its own slug and name, so there is nothing for a human to do first. */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ industrySlug: string }> },
): Promise<NextResponse> {
  try {
    const actor = await requireKnowledgeApprover();
    if (!actor) return unauthorized();
    const { industrySlug } = await params;
    return NextResponse.json(await importAuthoredPack(actor, industrySlug));
  } catch (error) {
    return errorResponse(error);
  }
}
