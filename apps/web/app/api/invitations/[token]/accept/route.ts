import { NextResponse } from "next/server";
import { errorResponse } from "@/lib/api/respond";
import { SESSION_COOKIE, sessionCookieOptions, SESSION_TTL_SECONDS } from "@/lib/auth/config";
import { checkRateLimit } from "@/lib/auth/rate-limit";
import { signSession } from "@/lib/auth/session";
import { toSessionUser, type SessionPayload } from "@/lib/auth/types";
import { acceptInvitation } from "@/lib/invitations/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ token: string }>;
}

/** Public: accept an invitation — creates the organization + user account, marks the token
 * used, and signs the visitor straight into their new workspace (USER FLOW). Throttled by IP;
 * this endpoint has no session to key on yet. */
export async function POST(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
    const limit = await checkRateLimit(`accept-invite:${ip}`);
    if (!limit.allowed) {
      return NextResponse.json(
        { error: "Too many attempts. Please try again shortly." },
        { status: 429, headers: { "Retry-After": String(limit.retryAfterSeconds) } },
      );
    }

    const { token } = await params;
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json({ error: "Malformed request body." }, { status: 400 });
    }

    const accepted = await acceptInvitation(token, body);

    const initials =
      accepted.name
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() ?? "")
        .join("") || "?";

    const payload: SessionPayload = {
      userId: accepted.userId,
      email: accepted.email,
      name: accepted.name,
      initials,
      organizationId: accepted.organizationId,
      organizationName: accepted.organizationName,
      roles: [accepted.role],
      // Placeholder — see lib/auth/users.ts for why this does not yet authenticate to apps/api.
      apiToken: `web-user:${accepted.userId}`,
    };
    const session = await signSession(payload);

    const response = NextResponse.json({ user: toSessionUser(payload) }, { status: 201 });
    response.cookies.set(SESSION_COOKIE, session, sessionCookieOptions(SESSION_TTL_SECONDS));
    return response;
  } catch (error) {
    return errorResponse(error);
  }
}
