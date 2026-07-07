import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { approveAccessRequest } from "@/lib/accessRequests/service";
import { requireAdminActor } from "../../_adminGuard";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Approve a pending access request — creates a one-time invitation for the requester and
 * emails them the invite link (KI-P9 Resend integration). The link is also returned here so
 * the admin can copy/resend it manually — a mail-provider failure never hides it. */
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

    const result = await approveAccessRequest(actor, id, body, new URL(request.url).origin);

    return NextResponse.json({
      accessRequest: result.accessRequest,
      inviteLink: result.inviteLink,
      expiresAt: result.invitation.expiresAt,
      emailSent: result.emailSent,
    });
  } catch (error) {
    return errorResponse(error);
  }
}
