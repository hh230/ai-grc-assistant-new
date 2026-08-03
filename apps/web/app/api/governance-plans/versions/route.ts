import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getPlanVersions } from "@/lib/planExecution/service";

export const runtime = "nodejs";

/** The tenant's full plan lineage, oldest first (ADR 0066 §3.1) — how the user compares versions
 * over time. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const items = await getPlanVersions(actor);
    return NextResponse.json({ items });
  } catch (error) {
    return errorResponse(error);
  }
}
