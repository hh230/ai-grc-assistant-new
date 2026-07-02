# Security Posture — `@grc/web`

A summary of the security controls implemented in the web platform (P2–P10) and the
follow-ups recommended before a regulated production launch.

## Authentication & sessions

- **Sessions** are stateless HS256 JWTs (`jose`) stored in an **httpOnly, SameSite=Lax**
  cookie, `Secure` in production. 8-hour TTL. Signature + expiry + shape (zod) are verified
  on every request.
- **`AUTH_SECRET`** is mandatory in production — the app throws at startup if it is missing
  or shorter than 32 chars. A dev-only fallback exists and logs a warning.
- **Passwords** are hashed with `scrypt` (N=16384) and verified in constant time
  (`timingSafeEqual`). Login is **rate-limited** and returns a generic error (no user
  enumeration).
- **Logout** clears the cookie server-side.

## Authorization (RBAC) & tenancy

- A **default-deny** RBAC matrix (7 roles × Action × ResourceType) mirrors the backend and
  is enforced **server-side in every service** — the UI only mirrors it for affordances.
- **Consequential actions are human-gated**: publishing a policy and accepting a risk
  require the `approve`/`publish` permission (owners/admins/compliance/risk managers).
- **Tenant isolation** is enforced in every repository query and every storage key; a
  request can only ever reach its own tenant's data.
- Routes are protected by **edge middleware** (primary gate) and re-checked server-side in
  the authenticated layout (defense-in-depth).

## Input handling

- All request bodies are **schema-validated (zod)** at the boundary.
- Uploads are validated server-side for **size, MIME, and magic bytes** (content sniffing) —
  spoofed extensions are rejected.
- Filenames are sanitized (path components + control chars stripped); storage keys are
  opaque IDs, and the blob store guards against path traversal.
- LLM output is treated as untrusted: structured (JSON) responses are schema-validated;
  the assistant is instructed to ground answers and refuse when context is insufficient.

## Transport & headers

Applied to every response (`next.config.mjs`): **Content-Security-Policy**, **HSTS**
(`max-age` 2y, preload), **X-Frame-Options: DENY**, **X-Content-Type-Options: nosniff**,
**Referrer-Policy: strict-origin-when-cross-origin**, **Permissions-Policy** (camera/mic/geo
disabled). `X-Powered-By` is disabled.

## Data & AI

- Uploaded documents are stored per-tenant. Sending document text to OpenAI is a deliberate,
  Product-Owner-approved decision (ADL-0009); a **local, no-egress provider** is available
  behind the same port (`AI_PROVIDER=local`) for data-residency-sensitive tenants.
- No secrets in code — all config comes from the environment.

## Recommended production follow-ups

1. **Nonce-based CSP** — replace `script-src 'unsafe-inline'` with a per-request nonce.
2. **OIDC/SSO** — swap the seeded `AuthRepository` for an enterprise IdP (the seam exists).
3. **Postgres + object storage** — replace the filesystem repositories/blob store adapters.
4. **Distributed rate limiting** (Redis) and **audit-log persistence** (append-only).
5. **Dependency & secret scanning** in CI; periodic penetration testing.
