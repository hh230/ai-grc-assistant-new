/** Invite token generation/hashing (KI-P9, ADR-0034). The raw token is high-entropy and
 * random — it exists only in the invite URL (and, once wired, an invite email); only its
 * sha256 hash is ever persisted, so a database dump cannot hand out usable credentials.
 * Node-only. */

import { createHash, randomBytes } from "node:crypto";

const TOKEN_BYTES = 32; // 256 bits

export function generateInviteToken(): string {
  return randomBytes(TOKEN_BYTES).toString("hex");
}

export function hashInviteToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}
