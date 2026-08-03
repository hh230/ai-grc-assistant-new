/** Reset token generation/hashing — same shape as `lib/invitations/token.ts` (high-entropy
 * random token; only its sha256 hash is ever persisted). Node-only. */

import { createHash, randomBytes } from "node:crypto";

const TOKEN_BYTES = 32; // 256 bits

export function generateResetToken(): string {
  return randomBytes(TOKEN_BYTES).toString("hex");
}

export function hashResetToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}
