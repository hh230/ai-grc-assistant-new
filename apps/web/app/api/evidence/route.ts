import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { MAX_EVIDENCE_BYTES } from "@/lib/evidence/validation";
import { createEvidence, listEvidence } from "@/lib/evidence/service";
import { toEvidenceSummary } from "@/lib/evidence/types";

export const runtime = "nodejs";

export async function GET(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const url = new URL(request.url);
    const items = await listEvidence(actor, {
      search: url.searchParams.get("search") ?? undefined,
      tag: url.searchParams.get("tag") ?? undefined,
      controlId: url.searchParams.get("controlId") ?? undefined,
    });
    return NextResponse.json({ evidence: items.map(toEvidenceSummary) });
  } catch (error) {
    return errorResponse(error);
  }
}

function parseJsonArray(value: FormDataEntryValue | null): string[] {
  if (typeof value !== "string" || !value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();

    const form = await request.formData().catch(() => null);
    const file = form?.get("file");
    const title = form?.get("title");
    if (!(file instanceof File)) throw new ValidationError("A file is required.");
    if (typeof title !== "string" || !title.trim())
      throw new ValidationError("A title is required.");
    if (file.size > MAX_EVIDENCE_BYTES) {
      throw new ValidationError(
        `File exceeds the ${Math.round(MAX_EVIDENCE_BYTES / (1024 * 1024))} MB limit.`,
      );
    }

    const evidence = await createEvidence(actor, {
      title,
      description:
        typeof form?.get("description") === "string"
          ? (form.get("description") as string)
          : undefined,
      tags: parseJsonArray(form?.get("tags") ?? null),
      controlIds: parseJsonArray(form?.get("controlIds") ?? null),
      file: {
        fileName: file.name,
        contentType: file.type,
        bytes: Buffer.from(await file.arrayBuffer()),
      },
    });
    return NextResponse.json({ evidence }, { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}
