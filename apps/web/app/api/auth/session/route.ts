import { NextResponse } from "next/server";
import { getSessionUser } from "@/lib/auth/server";

export const runtime = "nodejs";

/** Returns the current public session user, or `null` when unauthenticated. */
export async function GET(): Promise<NextResponse> {
  const user = await getSessionUser();
  return NextResponse.json({ user });
}
