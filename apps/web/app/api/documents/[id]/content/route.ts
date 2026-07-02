import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { readDocumentBytes } from "@/lib/documents/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Streams the stored file back for inline viewing/download (tenant-scoped). */
export async function GET(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const { doc, bytes } = await readDocumentBytes(actor, id);

    const disposition =
      new URL(request.url).searchParams.get("download") !== null ? "attachment" : "inline";
    return new NextResponse(new Uint8Array(bytes), {
      status: 200,
      headers: {
        "Content-Type": doc.contentType,
        "Content-Length": String(bytes.length),
        "Content-Disposition": `${disposition}; filename="${encodeURIComponent(doc.fileName)}"`,
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    return errorResponse(error);
  }
}
