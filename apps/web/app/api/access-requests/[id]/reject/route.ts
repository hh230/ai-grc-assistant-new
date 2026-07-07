import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { rejectAccessRequest } from "@/lib/accessRequests/service";
import { requireAdminActor } from "../../_adminGuard";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Reject a pending access request. No invitation is created. */
export async function POST(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const accessRequest = await rejectAccessRequest(actor, id);
    return NextResponse.json({ accessRequest });
  } catch (error) {
    return errorResponse(error);
  }
}
