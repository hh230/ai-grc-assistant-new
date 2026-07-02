import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { readEvidenceVersion } from "@/lib/evidence/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string; versionId: string }>;
}

/** Streams a specific evidence version's file (tenant-scoped). */
export async function GET(request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id, versionId } = await params;
    const { version, bytes } = await readEvidenceVersion(actor, id, versionId);

    const disposition =
      new URL(request.url).searchParams.get("download") !== null ? "attachment" : "inline";
    return new NextResponse(new Uint8Array(bytes), {
      status: 200,
      headers: {
        "Content-Type": version.contentType,
        "Content-Length": String(bytes.length),
        "Content-Disposition": `${disposition}; filename="${encodeURIComponent(version.fileName)}"`,
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    return errorResponse(error);
  }
}
