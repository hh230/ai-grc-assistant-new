import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { updateWorkerSchedule } from "@/lib/knowledgeWorker/service";
import type { ScheduleUpdate } from "@/lib/knowledgeWorker/types";
import { requireAdminActor } from "../_adminGuard";

export const runtime = "nodejs";

/** Enable/disable the worker and/or change its learning-cycle interval, proxied to apps/api
 * (which authorizes, applies the change, and records the audit event). */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const body = (await request.json().catch(() => ({}))) as ScheduleUpdate;
    const control = await updateWorkerSchedule(actor, body);
    return NextResponse.json(control);
  } catch (error) {
    return errorResponse(error);
  }
}
