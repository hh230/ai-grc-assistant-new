import { NextResponse } from "next/server";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { checkRateLimit } from "@/lib/auth/rate-limit";
import { listAccessRequests, submitAccessRequest } from "@/lib/accessRequests/service";
import { requireAdminActor } from "./_adminGuard";

export const runtime = "nodejs";

/** Public: submit a request for access to the platform. Throttled by IP — this endpoint has
 * no session to key on. */
export async function POST(request: Request): Promise<NextResponse> {
  try {
    const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
    const limit = await checkRateLimit(`access-request:${ip}`);
    if (!limit.allowed) {
      return NextResponse.json(
        { error: "Too many requests. Please try again shortly." },
        { status: 429, headers: { "Retry-After": String(limit.retryAfterSeconds) } },
      );
    }

    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json({ error: "Malformed request body." }, { status: 400 });
    }

    const accessRequest = await submitAccessRequest(body);
    return NextResponse.json({ accessRequest }, { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}

/** Admin: list access requests, optionally filtered by `?status=pending|approved|rejected`. */
export async function GET(request: Request): Promise<NextResponse> {
  try {
    const actor = await requireAdminActor();
    if (!actor) return unauthorized();

    const statusParam = new URL(request.url).searchParams.get("status");
    const status =
      statusParam === "pending" || statusParam === "approved" || statusParam === "rejected"
        ? statusParam
        : undefined;

    const requests = await listAccessRequests(status);
    return NextResponse.json({ requests });
  } catch (error) {
    return errorResponse(error);
  }
}
