import { NextResponse } from "next/server";
import { getActor } from "@/lib/auth/actor";
import { errorResponse, unauthorized } from "@/lib/api/respond";
import { ForbiddenError } from "@/lib/errors";
import { can } from "@/lib/auth/permissions";
import { FRAMEWORKS, allControls } from "@/lib/frameworks/catalog";

export const runtime = "nodejs";

/** Read-only framework/control catalog (reference data) for pickers and governance views. */
export async function GET(): Promise<NextResponse> {
  try {
    const actor = await getActor();
    if (!actor) return unauthorized();
    if (!can(actor.roles, "read", "framework")) {
      throw new ForbiddenError("You are not permitted to view frameworks.");
    }
    return NextResponse.json({
      frameworks: FRAMEWORKS.map(({ controls, ...framework }) => ({
        ...framework,
        controlCount: controls.length,
      })),
      controls: allControls(),
    });
  } catch (error) {
    return errorResponse(error);
  }
}
