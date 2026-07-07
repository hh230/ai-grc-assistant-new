import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { listPendingRegulationVersions } from "@/lib/regulationReview/service";
import { requireAdminActor } from "../_adminGuard";

export const runtime = "nodejs";

/** Regulation versions awaiting admin approval, proxied from apps/api. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const versions = await listPendingRegulationVersions(actor);
    return NextResponse.json({ versions });
  } catch (error) {
    return errorResponse(error);
  }
}
