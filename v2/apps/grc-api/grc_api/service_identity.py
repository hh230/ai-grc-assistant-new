"""`ServiceAssertionIdentityProvider` — the interim identity bridge from `apps/web` (ADR 0066
addendum "Frontend integration").

`security.py` already designed the seam this slots into: `require_tenant` depends only on the
`IdentityProvider` Protocol, so deployment can swap providers with **zero route change** — that
docstring specifically calls out "an OIDC provider... same return type." This is that swap, done
now rather than later, because the Governance Discovery feature is the first thing in this
codebase that needs `apps/web` to reach a `v2/apps/*` host at all (see ADR 0066).

`apps/web` is a trusted backend caller acting on behalf of an already-authenticated user session —
it has already resolved the human's tenant/org via its own auth and Postgres-backed session model.
Rather than teaching `grc-api` a second copy of that user database, `apps/web`'s server-side proxy
route ASSERTS the identity via a short-lived, HMAC-signed token instead of grc-api re-deriving it.
This is a standard trusted-BFF pattern (the browser never sees the signing secret or the token —
both are server-only), not a general-purpose credential, and it is explicitly interim: real
identity federation (OIDC/SSO, CLAUDE.md §20) replaces this provider with zero route change, by
design, the same way this provider replaced nothing in the existing dev provider.

Token shape (no new dependency — stdlib `hmac`/`hashlib`/`json`/`base64`/`time` only):
    "<base64url(json_payload)>.<hex(hmac_sha256(secret, json_payload_bytes))>"
    payload = {"tenant_id", "principal_id", "roles": [...], "region", "exp": <unix_ts>}

The signature is computed over the RAW payload bytes actually transmitted (never a re-serialized
copy), so there is no JSON key-ordering ambiguity between signer and verifier.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Sequence
from typing import Any

from pipeline_contracts import TenantContext

# Tokens are minted fresh per outgoing request (apps/web never caches or reuses one) — a short
# window bounds the blast radius of a leaked token without requiring clock-skew tolerance logic.
DEFAULT_TTL_SECONDS = 60


class ServiceAssertionIdentityProvider:
    """Verifies a signed identity assertion minted by a trusted backend caller. The secret must be
    the same value the caller signs with (`GRC_API_SERVICE_SECRET` on both sides) — never logged,
    never sent to a browser.

    **Accepts MORE THAN ONE secret, so the key can be rotated without downtime.** With a single
    accepted value, rotation requires `apps/web` and `grc-api` to change at the same instant, and
    any skew rejects every request in between — which means the first time you attempt a rotation
    is during a security incident, and you discover then that you cannot.

    Verification tries each accepted secret in order and succeeds if any matches. Rotation is
    therefore:

        1. add the new secret to grc-api's accepted list  → deploy
        2. switch apps/web to MINT with the new secret    → deploy
        3. remove the old secret from the accepted list   → deploy

    Tokens live `DEFAULT_TTL_SECONDS` (60s) and are minted fresh per request, so the overlap
    window need only exceed 60 seconds. At no point is a valid request rejected.

    Every candidate is compared with `hmac.compare_digest` and the loop does not stop early on a
    mismatch, so the number of secrets configured is not observable from response timing.
    """

    def __init__(self, secret: str | Sequence[str]) -> None:
        candidates = [secret] if isinstance(secret, str) else list(secret)
        # Stripped, not merely truthy: "   " is a truthy string but not a secret, and accepting it
        # would turn a whitespace-only configuration value into a guessable signing key.
        accepted = [value.strip().encode("utf-8") for value in candidates if value.strip()]
        if not accepted:
            raise ValueError("ServiceAssertionIdentityProvider requires at least one secret")
        self._secrets = tuple(accepted)

    def resolve(self, credential: str) -> TenantContext | None:
        payload_b64, sep, signature_hex = credential.partition(".")
        if not sep or not payload_b64 or not signature_hex:
            return None
        try:
            padded = payload_b64 + "=" * (-len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(padded)
        except (ValueError, TypeError):
            return None
        # Constant work regardless of which secret matches, or whether any does: every candidate
        # is compared, so response timing never reveals how many keys are in rotation.
        matched = False
        for secret in self._secrets:
            expected = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
            matched |= hmac.compare_digest(expected, signature_hex)
        if not matched:
            return None
        try:
            payload: dict[str, Any] = json.loads(payload_bytes)
        except ValueError:
            return None
        if float(payload.get("exp", 0)) < time.time():
            return None
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return None
        return TenantContext(
            tenant_id=tenant_id,
            principal_id=payload.get("principal_id", ""),
            roles=tuple(payload.get("roles", ())),
            region=payload.get("region", ""),
        )


def mint_service_assertion(
    *,
    secret: str,
    tenant_id: str,
    principal_id: str = "",
    roles: tuple[str, ...] = (),
    region: str = "",
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    """The Python-side mirror of the token-minting logic `apps/web` implements in TypeScript
    (`apps/web/lib/grcApi/serviceToken.ts`) — used here only for tests/dev tooling parity; the
    real minting for live traffic happens on the Node side."""
    payload = {
        "tenant_id": tenant_id,
        "principal_id": principal_id,
        "roles": list(roles),
        "region": region,
        "exp": time.time() + ttl_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode("ascii")
    return f"{payload_b64}.{signature}"


class CompositeIdentityProvider:
    """Tries each provider in order, returning the first resolved `TenantContext`. Lets the dev
    fixed-credential provider and the service-assertion provider coexist without either route or
    the `require_tenant` dependency knowing there is more than one (`security.py`'s whole point)."""

    def __init__(self, providers: tuple[Any, ...]) -> None:
        self._providers = providers

    def resolve(self, credential: str) -> TenantContext | None:
        for provider in self._providers:
            tenant = provider.resolve(credential)
            if tenant is not None:
                return tenant
        return None
