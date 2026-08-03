import { NextResponse } from "next/server";
import { z } from "zod";
import { checkRateLimit } from "@/lib/auth/rate-limit";
import { requestPasswordReset } from "@/lib/passwordReset/service";

// scrypt (via hashPassword, reached indirectly on reset) requires the Node.js runtime.
export const runtime = "nodejs";

const forgotPasswordSchema = z.object({ email: z.string().trim().email() });

/** Public: requests a password-reset email. Always responds with the same generic message
 * regardless of whether the address has an account — never reveal user existence. */
export async function POST(request: Request): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Malformed request body." }, { status: 400 });
  }

  const parsed = forgotPasswordSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "A valid email is required." }, { status: 400 });
  }
  const { email } = parsed.data;

  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const limit = await checkRateLimit(`forgot-password:${ip}:${email.toLowerCase()}`);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: "Too many attempts. Please try again shortly." },
      { status: 429, headers: { "Retry-After": String(limit.retryAfterSeconds) } },
    );
  }

  await requestPasswordReset(email, new URL(request.url).origin);

  return NextResponse.json({
    message: "If that email has an account, we've sent a password reset link.",
  });
}
