import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { listOrganizationMembers } from "@/lib/organizations/service";

export const runtime = "nodejs";

/** Real members plus any still-open invitations for the caller's current organization —
 * backs Settings > Team. Any authenticated member of the org may view it. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const team = await listOrganizationMembers(actor);
    return NextResponse.json(team);
  } catch (error) {
    return errorResponse(error);
  }
}
