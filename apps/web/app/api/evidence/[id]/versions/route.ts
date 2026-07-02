import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { MAX_EVIDENCE_BYTES } from "@/lib/evidence/validation";
import { addEvidenceVersion } from "@/lib/evidence/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Upload a new version of an evidence item (preserves prior versions). */
export async function POST(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;

    const form = await request.formData().catch(() => null);
    const file = form?.get("file");
    if (!(file instanceof File)) throw new ValidationError("A file is required.");
    if (file.size > MAX_EVIDENCE_BYTES) {
      throw new ValidationError(
        `File exceeds the ${Math.round(MAX_EVIDENCE_BYTES / (1024 * 1024))} MB limit.`,
      );
    }
    const note = typeof form?.get("note") === "string" ? (form.get("note") as string) : undefined;

    const evidence = await addEvidenceVersion(actor, id, {
      fileName: file.name,
      contentType: file.type,
      bytes: Buffer.from(await file.arrayBuffer()),
      note,
    });
    return NextResponse.json({ evidence }, { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}
