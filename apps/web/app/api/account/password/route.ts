import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/server";
import { checkRateLimit } from "@/lib/auth/rate-limit";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { changePassword } from "@/lib/account/service";

export const runtime = "nodejs";

/** Changes the signed-in user's password (requires the current password). Throttled per
 * account to slow a hijacked-session brute-forcing the current password. */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const session = await getSession();
    if (!session) return unauthorized();

    const limit = await checkRateLimit(`change-password:${session.userId}`);
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

    await changePassword(session, body);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
