import { NextResponse } from "next/server";
import { z } from "zod";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { deleteRisk, getRisk, updateRisk } from "@/lib/risk/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const risk = await getRisk(actor, id);
    return NextResponse.json({ risk });
  } catch (error) {
    return errorResponse(error);
  }
}

const patchSchema = z.object({
  title: z.string().min(1).optional(),
  description: z.string().optional(),
  category: z.string().optional(),
  likelihood: z.number().int().min(1).max(5).optional(),
  impact: z.number().int().min(1).max(5).optional(),
  ownerName: z.string().optional(),
  controlIds: z.array(z.string()).optional(),
  mitigationPlan: z.string().optional(),
  residualLikelihood: z.number().int().min(1).max(5).nullable().optional(),
  residualImpact: z.number().int().min(1).max(5).nullable().optional(),
});

export async function PATCH(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const parsed = patchSchema.safeParse(await request.json().catch(() => null));
    if (!parsed.success) throw new ValidationError("Invalid update payload.");
    const risk = await updateRisk(actor, id, parsed.data);
    return NextResponse.json({ risk });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function DELETE(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    await deleteRisk(actor, id);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
