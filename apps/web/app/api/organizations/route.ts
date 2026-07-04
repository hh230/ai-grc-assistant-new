import { NextResponse } from "next/server";
import { SESSION_COOKIE, sessionCookieOptions, SESSION_TTL_SECONDS } from "@/lib/auth/config";
import { getActor } from "@/lib/auth/actor";
import { getSession } from "@/lib/auth/server";
import { signSession } from "@/lib/auth/session";
import { toSessionUser, type SessionPayload } from "@/lib/auth/types";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { createOrganization, listMyOrganizations } from "@/lib/organizations/service";

export const runtime = "nodejs";

/** Every organization the signed-in user belongs to, plus which one is currently active. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const organizations = await listMyOrganizations(actor);
    return NextResponse.json({ organizations, activeOrganizationId: actor.tenantId });
  } catch (error) {
    return errorResponse(error);
  }
}

/** Creates a new organization, makes the caller its owner, and switches into it. */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    const session = await getSession();
    if (!actor || !session) return unauthorized();

    let body: unknown;
    try {
      body = await request.json();
    } catch {
      body = {};
    }
    const organization = await createOrganization(actor, body);

    const nextPayload: SessionPayload = {
      ...session,
      organizationId: organization.id,
      organizationName: organization.name,
      roles: ["owner"],
    };
    const token = await signSession(nextPayload);

    const response = NextResponse.json({
      organization,
      user: toSessionUser(nextPayload),
    });
    response.cookies.set(SESSION_COOKIE, token, sessionCookieOptions(SESSION_TTL_SECONDS));
    return response;
  } catch (error) {
    return errorResponse(error);
  }
}
