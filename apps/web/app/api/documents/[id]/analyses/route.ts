import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { listAnalysisVersions } from "@/lib/analysis/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Every analysis version for a document, newest first — powers history + version comparison. */
export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const versions = await listAnalysisVersions(actor, id);
    return NextResponse.json({ versions });
  } catch (error) {
    return errorResponse(error);
  }
}
