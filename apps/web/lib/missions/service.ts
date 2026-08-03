import type { ActorContext } from "@/lib/auth/actor";
import { missionsRepository } from "./repository";
import type { Mission } from "./types";

/** Lists every mission run for the actor's tenant (CLAUDE.md §20 — tenant-scoped by
 * construction, not by convention). */
export async function listMissions(actor: ActorContext): Promise<Mission[]> {
  return missionsRepository.listForTenant(actor.tenantId);
}
