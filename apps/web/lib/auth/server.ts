/**
 * Server-only session helpers for Server Components and Route Handlers. Reads the httpOnly
 * cookie via `next/headers`, so this must never be imported by client components or
 * middleware. Pairs with the edge `middleware.ts` (the primary gate) as defense-in-depth.
 */

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ACCESS_DENIED_PATH, LOGIN_PATH, SESSION_COOKIE } from "./config";
import { can, type Action, type ResourceType } from "./permissions";
import type { UserRole } from "./roles";
import { verifySessionToken } from "./session";
import { toSessionUser } from "./types";
import type { SessionPayload, SessionUser } from "./types";

export async function getSession(): Promise<SessionPayload | null> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return null;
  return verifySessionToken(token);
}

export async function getSessionUser(): Promise<SessionUser | null> {
  const session = await getSession();
  return session ? toSessionUser(session) : null;
}

/** Returns the session or redirects to login, preserving the intended destination. */
export async function requireSession(nextPath?: string): Promise<SessionPayload> {
  const session = await getSession();
  if (!session) {
    redirect(nextPath ? `${LOGIN_PATH}?next=${encodeURIComponent(nextPath)}` : LOGIN_PATH);
  }
  return session;
}

/** Requires at least one of `roles`; otherwise redirects to the access-denied page. */
export async function requireRoles(...roles: UserRole[]): Promise<SessionPayload> {
  const session = await requireSession();
  if (!roles.some((role) => session.roles.includes(role))) {
    redirect(ACCESS_DENIED_PATH);
  }
  return session;
}

/** Requires permission for `action` on `resource`; otherwise redirects to access-denied. */
export async function requirePermission(
  action: Action,
  resource: ResourceType,
): Promise<SessionPayload> {
  const session = await requireSession();
  if (!can(session.roles, action, resource)) {
    redirect(ACCESS_DENIED_PATH);
  }
  return session;
}
