import type { UserRole } from "./roles";

/**
 * The identity surfaced to the client (UI). Never carries secrets — no password hash and
 * no backend token. This is what `useSession()` exposes and what the workspace renders.
 */
export interface SessionUser {
  userId: string;
  email: string;
  name: string;
  initials: string;
  organizationId: string;
  organizationName: string;
  roles: UserRole[];
}

/**
 * The full session as encoded in the signed httpOnly cookie. Extends the public identity
 * with the backend bearer token used to call the FastAPI API server-side. The token never
 * leaves the server (httpOnly cookie + server-only helpers), so it is safe to keep here.
 */
export interface SessionPayload extends SessionUser {
  apiToken: string;
}

export function toSessionUser(payload: SessionPayload): SessionUser {
  const { apiToken: _apiToken, ...user } = payload;
  return user;
}
