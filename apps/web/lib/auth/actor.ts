/**
 * The actor context an API request runs under — the frontend analogue of the backend's
 * `ExecutionContext`/`Principal`. Carries tenant + identity + roles so services can scope
 * data and enforce RBAC. Server-only (reads the session cookie).
 */

import { getSession } from "./server";
import type { UserRole } from "./roles";

export interface ActorContext {
  userId: string;
  userName: string;
  tenantId: string;
  roles: UserRole[];
  /** Backend bearer token for this actor (used when proxying to the FastAPI API). */
  apiToken: string;
}

export async function getActor(): Promise<ActorContext | null> {
  const session = await getSession();
  if (!session) return null;
  return {
    userId: session.userId,
    userName: session.name,
    tenantId: session.organizationId,
    roles: session.roles,
    apiToken: session.apiToken,
  };
}
