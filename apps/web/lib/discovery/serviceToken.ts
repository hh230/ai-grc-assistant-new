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
import { UpstreamError } from "@/lib/errors";
import { logger } from "@/lib/observability/logger";

const DEFAULT_TTL_SECONDS = 60;

export interface ServiceAssertionSubject {
  tenantId: string;
  principalId?: string;
  roles?: readonly string[];
  region?: string;
}

/**
 * The secret is MANDATORY in every environment — there is deliberately no default and no dev
 * fallback (unlike `AUTH_SECRET`, which does fall back in dev). A shared default here would let
 * anyone mint an identity assertion for ANY tenant, breaking tenant isolation (CLAUDE.md §20),
 * so an unconfigured deployment must never be able to reach grc-api at all.
 *
 * What it must NOT do is crash the page. This throws a typed `UpstreamError` rather than a bare
 * `Error` so the failure travels the same path every other grc-api failure already travels:
 * `lib/api/respond.ts` maps it to the documented 502 (apps/web/README.md — "these three routes
 * 401/502 until it's running and configured") instead of an unmapped 500, and page-level callers
 * see the `AppError` type they already handle instead of an unhandled exception escaping the
 * Server Component render. `unreachable` stays false on purpose: this is a misconfiguration, not
 * a transient blip, so it must NOT be silently degraded into "no active plan" — a tenant that
 * really has a governance plan can never be shown "you have none" because of a config error.
 */
function serviceSecret(): string {
  // Comma-separated to support rotation without downtime: grc-api ACCEPTS every listed secret,
  // while this side always MINTS with the first. A rotation is therefore three deploys with no
  // window in which a valid request is rejected —
  //   1. add the new secret to grc-api's list      (it now accepts both)
  //   2. put the new secret first here             (it now mints with the new one)
  //   3. drop the old secret from grc-api's list   (the old key is revoked)
  // Tokens live 60s, so each overlap need only outlast that.
  //
  // Blank entries are dropped rather than trusted: a trailing comma, or a whitespace-only value
  // from a secret manager, must never become a guessable signing key.
  const configured = (process.env.GRC_API_SERVICE_SECRET ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  const signingSecret = configured[0];
  if (signingSecret === undefined) {
    logger.error("grc_api_service_secret_missing", undefined, {
      remediation:
        "Set GRC_API_SERVICE_SECRET (see apps/web/.env.example) to the same value the grc-api " +
        "process uses. Required by /discovery, /plan, and Mission approvals (ADR 0066). " +
        "During a key rotation this may be a comma-separated list; the FIRST entry is the one " +
        "used to sign.",
    });
    throw new UpstreamError("The governance backend is not configured.");
  }
  return signingSecret;
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
