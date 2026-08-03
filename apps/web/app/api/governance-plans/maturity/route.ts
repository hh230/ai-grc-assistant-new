import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { getCurrentMaturity } from "@/lib/planExecution/service";

export const runtime = "nodejs";

/** The live, reversible maturity picture (ADR 0066 §5.3) — recomputed fresh from the frozen
 * Discovery baseline plus whichever plan items are CURRENTLY done, every call. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const maturity = await getCurrentMaturity(actor);
    return NextResponse.json(maturity);
  } catch (error) {
    return errorResponse(error);
  }
}
