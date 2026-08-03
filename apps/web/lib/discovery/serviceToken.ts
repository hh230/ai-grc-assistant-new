/**
 * Mints the short-lived, HMAC-signed identity assertion `apps/web` presents to `v2/apps/grc-api`
 * (ADR 0066 addendum "Frontend integration"). grc-api's `require_tenant` depends only on the
 * `IdentityProvider` Protocol (`v2/apps/grc-api/grc_api/security.py`) — this is the interim
 * provider that seam is designed to be swapped for real OIDC/SSO federation later (CLAUDE.md §20),
 * with zero route change on the grc-api side, by construction.
 *
 * `apps/web` is a trusted backend caller: it has already authenticated the human via its own
 * session (`getActor()`) and asserts that resolved identity — the secret and every minted token
 * are server-only, the browser never sees either. A token is minted fresh per outgoing request
 * (never cached/reused), with a short TTL, to bound the blast radius of a leaked value.
 *
 * Byte-for-byte mirror of `v2/apps/grc-api/grc_api/service_identity.py`'s `mint_service_assertion`
 * / `ServiceAssertionIdentityProvider` — the signature covers the RAW payload bytes actually sent,
 * so there is no JSON key-ordering ambiguity between signer and verifier.
 */

import { createHmac } from "node:crypto";

const DEFAULT_TTL_SECONDS = 60;

export interface ServiceAssertionSubject {
  tenantId: string;
  principalId?: string;
  roles?: readonly string[];
  region?: string;
}

function serviceSecret(): string {
  const secret = process.env.GRC_API_SERVICE_SECRET;
  if (!secret) {
    throw new Error(
      "GRC_API_SERVICE_SECRET is not set — required to call v2/apps/grc-api (ADR 0066).",
    );
  }
  return secret;
}

/** Mints a fresh, short-lived signed assertion for the given subject. Server-only (uses `node:crypto`). */
export function mintGrcApiServiceToken(
  subject: ServiceAssertionSubject,
  ttlSeconds: number = DEFAULT_TTL_SECONDS,
): string {
  const secret = serviceSecret();
  const payload = {
    tenant_id: subject.tenantId,
    principal_id: subject.principalId ?? "",
    roles: subject.roles ? [...subject.roles] : [],
    region: subject.region ?? "",
    exp: Math.floor(Date.now() / 1000) + ttlSeconds,
  };
  const payloadBytes = Buffer.from(JSON.stringify(payload), "utf-8");
  const signature = createHmac("sha256", secret).update(payloadBytes).digest("hex");
  const payloadB64Url = payloadBytes.toString("base64url");
  return `${payloadB64Url}.${signature}`;
}
