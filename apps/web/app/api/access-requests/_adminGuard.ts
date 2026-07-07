/** Shared admin-only guard for every `/api/access-requests/*` route handler that reviews
 * requests (KI-P9, ADR-0034). Mirrors `app/api/regulation-review/_adminGuard.ts` exactly —
 * submitting a request is public; reviewing one is owner/admin only. */

import { getActor, type ActorContext } from "@/lib/auth/actor";
import { ForbiddenError } from "@/lib/errors";

export async function requireAdminActor(): Promise<ActorContext | null> {
  const actor = await getActor();
  if (!actor) return null;
  if (!actor.roles.includes("owner") && !actor.roles.includes("admin")) {
    throw new ForbiddenError("Only workspace owners and admins may review access requests.");
  }
  return actor;
}
