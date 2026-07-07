import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { approveRegulationVersion } from "@/lib/regulationReview/service";
import { requireAdminActor } from "../../_adminGuard";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ versionId: string }>;
}

/** Approve a pending regulation version — triggers embedding generation for its sections,
 * proxied from apps/api. */
export async function POST(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const { versionId } = await params;
    const result = await approveRegulationVersion(actor, versionId);
    return NextResponse.json(result);
  } catch (error) {
    return errorResponse(error);
  }
}
