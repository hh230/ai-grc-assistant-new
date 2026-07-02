import { NextResponse } from "next/server";
import { z } from "zod";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { transitionRisk } from "@/lib/risk/service";
import { RISK_STATUSES } from "@/lib/risk/types";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

const statusSchema = z.object({ status: z.enum(RISK_STATUSES) });

/** Move a risk through its workflow. Accepting a risk is a human-gated action. */
export async function POST(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const parsed = statusSchema.safeParse(await request.json().catch(() => null));
    if (!parsed.success) throw new ValidationError("A valid status is required.");
    const risk = await transitionRisk(actor, id, parsed.data.status);
    return NextResponse.json({ risk });
  } catch (error) {
    return errorResponse(error);
  }
}
