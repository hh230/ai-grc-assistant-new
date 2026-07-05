import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { reviewPolicyQuality } from "@/lib/policyIntelligence/service";

export const runtime = "nodejs";

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** One policy's quality review (Policy Analyst), proxied from apps/api. */
export async function GET(_request: Request, { params }: RouteContext): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    const { id } = await params;
    const review = await reviewPolicyQuality(actor, id);
    return NextResponse.json(review);
  } catch (error) {
    return errorResponse(error);
  }
}
