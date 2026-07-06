import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getWorkerStatus } from "@/lib/knowledgeWorker/service";
import { requireAdminActor } from "../_adminGuard";

export const runtime = "nodejs";

/** The Autonomous Knowledge Worker's current status, proxied from apps/api. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const status = await getWorkerStatus(actor);
    return NextResponse.json(status);
  } catch (error) {
    return errorResponse(error);
  }
}
