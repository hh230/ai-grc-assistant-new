import { NextResponse } from "next/server";
import { SESSION_COOKIE, sessionCookieOptions } from "@/lib/auth/config";

export const runtime = "nodejs";

export async function POST(): Promise<NextResponse> {
  const response = NextResponse.json({ ok: true });
  // Overwrite with an immediately-expired cookie to clear the session.
  response.cookies.set(SESSION_COOKIE, "", sessionCookieOptions(0));
  return response;
}
