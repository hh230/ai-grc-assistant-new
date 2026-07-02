import { NextResponse } from "next/server";
import { z } from "zod";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { deleteEvidence, getEvidence, updateEvidence } from "@/lib/evidence/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const evidence = await getEvidence(actor, id);
    return NextResponse.json({ evidence });
  } catch (error) {
    return errorResponse(error);
  }
}

const patchSchema = z.object({
  title: z.string().min(1).optional(),
  description: z.string().optional(),
  tags: z.array(z.string()).optional(),
  controlIds: z.array(z.string()).optional(),
});

export async function PATCH(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const body = await request.json().catch(() => null);
    const parsed = patchSchema.safeParse(body);
    if (!parsed.success) throw new ValidationError("Invalid update payload.");
    const evidence = await updateEvidence(actor, id, parsed.data);
    return NextResponse.json({ evidence });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function DELETE(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    await deleteEvidence(actor, id);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
