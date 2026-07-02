import { NextResponse } from "next/server";
import { z } from "zod";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { createPolicy, listPolicies } from "@/lib/policies/service";
import { toPolicySummary } from "@/lib/policies/types";

export const runtime = "nodejs";

export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const policies = await listPolicies(actor);
    return NextResponse.json({ policies: policies.map(toPolicySummary) });
  } catch (error) {
    return errorResponse(error);
  }
}

const createSchema = z.object({
  title: z.string().trim().min(1),
  summary: z.string().optional(),
  body: z.string().optional(),
  ownerName: z.string().optional(),
  controlIds: z.array(z.string()).optional(),
});

export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const parsed = createSchema.safeParse(await request.json().catch(() => null));
    if (!parsed.success) throw new ValidationError("A title is required.");
    const policy = await createPolicy(actor, parsed.data);
    return NextResponse.json({ policy }, { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}
