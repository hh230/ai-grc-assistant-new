import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { approveAccessRequest } from "@/lib/accessRequests/service";
import { requireAdminActor } from "../../_adminGuard";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Approve a pending access request — creates a one-time invitation for the requester.
 * No email integration yet (ADR-0034 "Known limitations"): the invite link is returned here
 * for the admin to copy and send manually. */
export async function POST(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();
    const { id } = await params;

    let body: unknown = {};
    try {
      body = await request.json();
    } catch {
      body = {};
    }

    const result = await approveAccessRequest(actor, id, body);
    const inviteLink = new URL(
      `/accept-invite?token=${encodeURIComponent(result.token)}`,
      new URL(request.url).origin,
    ).toString();

    return NextResponse.json({
      accessRequest: result.accessRequest,
      inviteLink,
      expiresAt: result.invitation.expiresAt,
    });
  } catch (error) {
    return errorResponse(error);
  }
}
