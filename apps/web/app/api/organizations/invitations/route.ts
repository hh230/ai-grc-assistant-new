import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { checkRateLimit } from "@/lib/auth/rate-limit";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { inviteTeamMember } from "@/lib/organizations/service";

export const runtime = "nodejs";

/** Invite someone into the caller's current organization (owner/admin only — enforced in
 * `inviteTeamMember` itself, the single chokepoint every caller passes through). Throttled
 * per account, since each invite sends a real email. */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();

    const limit = await checkRateLimit(`invite-member:${actor.userId}`);
    if (!limit.allowed) {
      return NextResponse.json(
        { error: "Too many attempts. Please try again shortly." },
        { status: 429, headers: { "Retry-After": String(limit.retryAfterSeconds) } },
      );
    }

    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json({ error: "Malformed request body." }, { status: 400 });
    }

    const result = await inviteTeamMember(actor, body, new URL(request.url).origin);
    return NextResponse.json(
      {
        invitation: result.invitation,
        inviteLink: result.inviteLink,
        expiresAt: result.invitation.expiresAt,
        emailSent: result.emailSent,
      },
      { status: 201 },
    );
  } catch (error) {
    return errorResponse(error);
  }
}
