import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { inviteTeamMember } from "@/lib/organizations/service";

export const runtime = "nodejs";

/** Invite someone into the caller's current organization (owner/admin only — enforced in
 * `inviteTeamMember` itself, the single chokepoint every caller passes through). */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();

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
