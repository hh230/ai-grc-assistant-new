import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { listWorkerRuns } from "@/lib/knowledgeWorker/service";
import { requireAdminActor } from "../_adminGuard";

export const runtime = "nodejs";

/** The worker's recent learning-cycle run history, proxied from apps/api. */
export async function GET(request: Request): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const limitParam = new URL(request.url).searchParams.get("limit");
    const limit = limitParam ? Number(limitParam) : undefined;
    const runs = await listWorkerRuns(actor, limit);
    return NextResponse.json({ runs });
  } catch (error) {
    return errorResponse(error);
  }
}
