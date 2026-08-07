import { getActor } from "@/lib/auth/actor";
import { ForbiddenError } from "@/lib/errors";
import { isKnowledgeApprover } from "@/lib/knowledge/service";
import type { ActorContext } from "@/lib/auth/actor";

/**
 * Resolves the caller and refuses anyone who does not govern knowledge — **server-side**, on every
 * knowledge route, not by hiding a button. grc-api enforces the same rule again in its Application
 * layer; this one exists so a request that was never going to be allowed does not travel.
 *
 * Returns `null` when unauthenticated so the route can answer `401` rather than `403` — "who are
 * you?" and "not you" are different answers and a client acts on them differently.
 */
export async function requireKnowledgeApprover(): Promise<ActorContext | null> {
  const actor = await getActor();
  if (!actor) return null;
  if (!isKnowledgeApprover(actor)) {
    throw new ForbiddenError("Governing sector knowledge requires the knowledge approver role.");
  }
  return actor;
}
