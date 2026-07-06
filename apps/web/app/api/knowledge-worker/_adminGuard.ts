/** Shared admin-only guard for every `/api/knowledge-worker/*` route handler. Defense in
 * depth (CLAUDE.md §20): `apps/api`'s RBAC gate is the authoritative check, but this app
 * never even proxies the call for a non-admin actor. */

import { getActor, type ActorContext } from "@/lib/auth/actor";
import { ForbiddenError } from "@/lib/errors";

export async function requireAdminActor(): Promise<ActorContext | null> {
  const actor = await getActor();
  if (!actor) return null;
  if (!actor.roles.includes("owner") && !actor.roles.includes("admin")) {
    throw new ForbiddenError(
      "Only workspace owners and admins may access the AI Worker Control Center.",
    );
  }
  return actor;
}
