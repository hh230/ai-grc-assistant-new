/**
 * Stateless session tokens. Edge-safe (uses `jose`, no Node-only APIs) so the same
 * verify path runs in middleware and in server components. The token is an HS256 JWT
 * holding the full `SessionPayload`, signed with `AUTH_SECRET`.
 */

import { SignJWT, jwtVerify } from "jose";
import { z } from "zod";
import { getAuthSecret, JWT_ISSUER, SESSION_TTL_SECONDS } from "./config";
import { USER_ROLES } from "./roles";
import type { SessionPayload } from "./types";

const sessionSchema = z.object({
  userId: z.string().min(1),
  email: z.string().email(),
  name: z.string().min(1),
  initials: z.string().min(1),
  organizationId: z.string().min(1),
  organizationName: z.string().min(1),
  roles: z.array(z.enum(USER_ROLES)).min(1),
  apiToken: z.string().min(1),
});

export async function signSession(payload: SessionPayload): Promise<string> {
  return new SignJWT({ ...payload })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuedAt()
    .setIssuer(JWT_ISSUER)
    .setExpirationTime(`${SESSION_TTL_SECONDS}s`)
    .sign(getAuthSecret());
}

/** Verify signature + expiry + shape. Returns null on any failure (default deny). */
export async function verifySessionToken(token: string): Promise<SessionPayload | null> {
  try {
    const { payload } = await jwtVerify(token, getAuthSecret(), { issuer: JWT_ISSUER });
    const parsed = sessionSchema.safeParse(payload);
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}
