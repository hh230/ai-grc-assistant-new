import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getLearningReports } from "@/lib/knowledgeWorker/service";
import { requireAdminActor } from "../_adminGuard";

export const runtime = "nodejs";

/** Learning reports: knowledge base coverage by verification status, proxied from apps/api. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const reports = await getLearningReports(actor);
    return NextResponse.json(reports);
  } catch (error) {
    return errorResponse(error);
  }
}
