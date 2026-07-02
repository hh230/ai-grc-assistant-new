import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ValidationError } from "@/lib/errors";
import { MAX_UPLOAD_BYTES } from "@/lib/documents/validation";
import { listDocuments, uploadDocument } from "@/lib/documents/service";
import { DOCUMENT_CATEGORIES, toDocumentDto, type DocumentCategory } from "@/lib/documents/types";

// Filesystem + crypto require the Node.js runtime.
export const runtime = "nodejs";

export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const docs = await listDocuments(actor);
    return NextResponse.json({ documents: docs.map(toDocumentDto) });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function POST(request: Request): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();

    const formData = await request.formData().catch(() => null);
    const file = formData?.get("file");
    if (!(file instanceof File)) {
      throw new ValidationError("No file provided.");
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      throw new ValidationError(
        `File exceeds the ${Math.round(MAX_UPLOAD_BYTES / (1024 * 1024))} MB limit.`,
      );
    }
    const category = formData?.get("category");
    if (typeof category !== "string" || !DOCUMENT_CATEGORIES.includes(category as DocumentCategory)) {
      throw new ValidationError("Select a document category before uploading.");
    }

    const bytes = Buffer.from(await file.arrayBuffer());
    const result = await uploadDocument(actor, {
      fileName: file.name,
      contentType: file.type,
      bytes,
      category: category as DocumentCategory,
    });
    return NextResponse.json(
      { document: toDocumentDto(result.document), duplicate: result.kind === "duplicate" },
      { status: result.kind === "duplicate" ? 200 : 201 },
    );
  } catch (error) {
    return errorResponse(error);
  }
}
