import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getRegulationVersionDetail } from "@/lib/regulationReview/service";
import { requireAdminActor } from "../_adminGuard";

export const runtime = "nodejs";

/** One regulation version's full extracted content (chapters/articles), proxied from apps/api. */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ versionId: string }> },
): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const { versionId } = await params;
    const detail = await getRegulationVersionDetail(actor, versionId);
    return NextResponse.json(detail);
  } catch (error) {
    return errorResponse(error);
  }
}
