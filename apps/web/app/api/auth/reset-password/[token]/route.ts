import { NextResponse } from "next/server";
import { errorResponse } from "@/lib/api/respond";
import { checkRateLimit } from "@/lib/auth/rate-limit";
import { previewResetToken, resetPassword } from "@/lib/passwordReset/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ token: string }>;
}

/** Public: preview a reset token (which account it belongs to) so the reset-password page can
 * render before the visitor sets a new password. Rejects used/expired/unknown tokens. */
export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const { token } = await params;
    const preview = await previewResetToken(token);
    return NextResponse.json({ reset: preview });
  } catch (error) {
    return errorResponse(error);
  }
}

/** Public: consumes a reset token and sets the new password. Throttled by IP; this endpoint
 * has no session to key on yet. */
export async function POST(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
    const limit = await checkRateLimit(`reset-password:${ip}`);
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

    await resetPassword(token, body);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
