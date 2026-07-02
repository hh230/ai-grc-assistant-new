import { NextResponse } from "next/server";
import { z } from "zod";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { createRisk, listRisks } from "@/lib/risk/service";
import { toRiskSummary } from "@/lib/risk/types";

export const runtime = "nodejs";

export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const risks = await listRisks(actor);
    return NextResponse.json({ risks: risks.map(toRiskSummary) });
  } catch (error) {
    return errorResponse(error);
  }
}

const createSchema = z.object({
  title: z.string().trim().min(1),
  description: z.string().optional(),
  category: z.string().optional(),
  likelihood: z.number().int().min(1).max(5).optional(),
  impact: z.number().int().min(1).max(5).optional(),
  ownerName: z.string().optional(),
  controlIds: z.array(z.string()).optional(),
  mitigationPlan: z.string().optional(),
});

export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const parsed = createSchema.safeParse(await request.json().catch(() => null));
    if (!parsed.success) throw new ValidationError("A title is required.");
    const risk = await createRisk(actor, parsed.data);
    return NextResponse.json({ risk }, { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}
