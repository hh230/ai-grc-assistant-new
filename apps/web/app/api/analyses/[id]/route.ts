import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { NotFoundError, ValidationError } from "@/lib/errors";
import { deleteAnalysis, getAnalysis, renameAnalysis } from "@/lib/analysis/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Fetch one specific analysis version by its own id. */
export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const analysis = await getAnalysis(actor, id);
    if (!analysis) throw new NotFoundError("Analysis not found.");
    return NextResponse.json({ analysis });
  } catch (error) {
    return errorResponse(error);
  }
}

/** Rename an analysis version (title only). */
export async function PATCH(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const body = await request.json().catch(() => null);
    const title = body && typeof body === "object" ? (body as { title?: unknown }).title : null;
    if (typeof title !== "string" || !title.trim()) {
      throw new ValidationError("A non-empty title is required.");
    }
    const analysis = await renameAnalysis(actor, id, title);
    return NextResponse.json({ analysis });
  } catch (error) {
    return errorResponse(error);
  }
}

/** Delete one analysis version. */
export async function DELETE(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    await deleteAnalysis(actor, id);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
