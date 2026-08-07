import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { registerIndustry } from "@/lib/knowledge/service";
import { requireKnowledgeApprover } from "../_guard";

export const runtime = "nodejs";

export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await requireKnowledgeApprover();
    if (!actor) return unauthorized();
    const body = (await request.json().catch(() => null)) as {
      slug?: string;
      canonicalNameAr?: string;
    } | null;
    if (!body?.slug || !body?.canonicalNameAr) {
      throw new ValidationError("slug and canonicalNameAr are required.");
    }
    await registerIndustry(actor, body.slug, body.canonicalNameAr);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return errorResponse(error);
  }
}
