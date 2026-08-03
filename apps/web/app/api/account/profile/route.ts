import { NextResponse } from "next/server";
import { SESSION_COOKIE, sessionCookieOptions, SESSION_TTL_SECONDS } from "@/lib/auth/config";
import { getSession } from "@/lib/auth/server";
import { toSessionUser } from "@/lib/auth/types";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { updateProfile } from "@/lib/account/service";

export const runtime = "nodejs";

/** Updates the signed-in user's display name and re-issues the session cookie so the new
 * name is reflected immediately (mirrors `app/api/organizations/switch/route.ts`). */
export async function PATCH(request: Request): Promise<NextResponse> {
  try {
    const session = await getSession();
    if (!session) return unauthorized();

    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json({ error: "Malformed request body." }, { status: 400 });
    }

    const { token, payload } = await updateProfile(session, body);

    const response = NextResponse.json({ user: toSessionUser(payload) });
    response.cookies.set(SESSION_COOKIE, token, sessionCookieOptions(SESSION_TTL_SECONDS));
    return response;
  } catch (error) {
    return errorResponse(error);
  }
}
