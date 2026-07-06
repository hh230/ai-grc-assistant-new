import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { listWorkerEvents } from "@/lib/knowledgeWorker/service";
import { requireAdminActor } from "../_adminGuard";

export const runtime = "nodejs";

/** The worker's recent activity timeline — operational events only, no raw model
 * reasoning — proxied from apps/api. */
export async function GET(request: Request): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const limitParam = new URL(request.url).searchParams.get("limit");
    const limit = limitParam ? Number(limitParam) : undefined;
    const events = await listWorkerEvents(actor, limit);
    return NextResponse.json({ events });
  } catch (error) {
    return errorResponse(error);
  }
}
