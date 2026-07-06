import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { triggerWorkerRun } from "@/lib/knowledgeWorker/service";
import { requireAdminActor } from "../_adminGuard";

export const runtime = "nodejs";

/** Admin "Run Learning Now" — requests an out-of-cycle learning run, proxied to apps/api. */
export async function POST(): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const control = await triggerWorkerRun(actor);
    return NextResponse.json(control);
  } catch (error) {
    return errorResponse(error);
  }
}
