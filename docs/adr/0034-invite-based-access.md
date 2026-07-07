# ADR 0034: Invite-Based Access & Organization Onboarding (KI-P9) — replacing demo login with production-ready request-access → approve → invite → accept onboarding

- Status: Accepted
- Date: 2026-07-07
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §9, §14, §15, §20, §21, §22, §23; ADR 0013, 0014

## Context

`apps/web` has never had real user accounts. Every login (`lib/auth/users.ts`) resolved
against a hardcoded `SEED_USERS` array — seven fixed accounts sharing one password
(`GrcDemo!2026`), all in one seeded tenant (`dev-org`) — and the login page offered
one-click buttons to fill those credentials in. There was no way for a real prospect to
get an account: only self-service *organization* creation existed
(`lib/organizations/service.ts#createOrganization`), gated behind already being logged in
as one of the seven demo users. This was adequate for building the product but is
incompatible with an MVP production launch: production must have neither a public open
signup (unvetted tenants) nor a shared demo password (CLAUDE.md §20's default-deny/least-
privilege posture).

This phase (KI-P9) is scoped, per explicit instruction, to exactly Authentication, Users,
Organizations, Invitations, and Access Requests — it does not touch RAG, the Knowledge
Worker, or the Saudi Regulations ingestion/review pipeline (ADR-0025–0032), all of which
remain exactly as they were.

## Decision

**A four-stage flow: request → approve → invite → accept**, replacing demo access
entirely.

**1. Migration (`apps/web/lib/db/migrations/0024_access_onboarding.sql`) — three new
tables.**
- `users(id, email, name, password_hash, created_at)` — the first real, Postgres-backed
  identity table. `user_organizations` (0012_organizations.sql) already modeled membership
  as a join table with no foreign key on `user_id` (there was no `users` table yet to
  reference), so this is purely additive.
- `access_requests(id, name, email, organization_name, role_title, message, status,
  created_at, reviewed_at, reviewed_by)` — the public request-access submission
  (`status`: `pending` | `approved` | `rejected`).
- `invitations(id, email, organization_name, invited_role, token_hash, expires_at,
  used_at, access_request_id, created_at)` — a one-time, expiring credential.
  `organization_name` is a plain column, not a foreign key: the organization it names does
  not exist yet when the invitation is created (see below).

**2. Domain modules, mirroring `lib/organizations`'s repository/service split exactly.**
- `lib/users/{types,repository}.ts` — `PostgresUsersRepository` (find by email/id, create).
- `lib/accessRequests/{types,repository,service,client}.ts` — `submitAccessRequest`
  (idempotent: a second submission from the same email while one is still pending returns
  the existing request rather than creating a duplicate), `listAccessRequests`,
  `approveAccessRequest`, `rejectAccessRequest`.
- `lib/invitations/{types,repository,service,token,client}.ts` — `createInvitation`,
  `previewInvitation` (public-safe fields only), `acceptInvitation`. Tokens are 256-bit
  random (`generateInviteToken`) and only their sha256 is ever persisted
  (`hashInviteToken`) — the same reasoning as never storing a plaintext password: a
  database dump must not hand out usable credentials.

**3. The organization is created at *accept* time, not at approval time.** An access
request's `organization_name` is free text from an unvetted visitor; provisioning a real
tenant for it before anyone has actually set a password would leave orphaned organizations
for every approved-but-never-accepted invite. `acceptInvitation` creates the organization,
the user, and the `user_organizations` membership, and marks the invitation used, all in
one transaction with `SELECT ... FOR UPDATE` on the invitation row — a second, racing
accept on the same token must not also succeed (CLAUDE.md §9, idempotent/retry-safe
consequential actions), not just be caught by an earlier, non-transactional read.

**4. `invited_role` (`owner` | `admin` | `member`) maps to the platform's real `UserRole`
roster at accept time** (`mapInvitedRoleToUserRole`): `owner`/`admin` pass through
unchanged (both already grant every action on every resource in
`lib/auth/permissions.ts`'s matrix — the invitee is that organization's only member either
way), `member` maps to `analyst` (a contributor role: can author operational work, cannot
approve/publish/delete). Kept as a 3-way choice on the admin approval form rather than
exposing the full 7-role matrix, since a request-access invite always seeds a brand-new,
single-member organization.

**5. Admin review surface — `/access-requests`, mirroring `/regulation-review` exactly.**
Server-guarded (`requireRoles("owner", "admin")`), a defense-in-depth
`app/api/access-requests/_adminGuard.ts`, a two-pane workspace (pending list + detail
panel with Approve/Reject). Approving surfaces the invite link
(`/accept-invite?token=...`) directly in the response for the admin to copy — there is no
email integration yet (see Consequences), so this is the only way the requester currently
receives it.

**6. Public surfaces.** `/request-access` (under `(marketing)`, reachable from
`MarketingNav`'s new "Request Access" button and the login page's new "Request access"
link) submits an `AccessRequest`. `/accept-invite` (a bare, no-chrome page mirroring
`/login`'s own layout) previews the invitation, collects a name + password, and on success
signs the visitor straight into their new workspace — the same session-cookie mechanism
`POST /api/auth/login` already uses. Both paths are added to `PUBLIC_MARKETING_PATHS`
(`lib/auth/config.ts`) so the edge middleware never demands a session for them.

**7. Demo login is removed, not left dormant.** `SEED_USERS` and `InMemoryAuthRepository`
are deleted from `lib/auth/users.ts`, replaced by a `PostgresAuthRepository` that resolves
a login against the real `users` table joined with the caller's earliest
`user_organizations` membership. `LoginForm`'s demo-account quick-fill buttons and the
`login.demoAccountsTitle`/`demoRoles` message keys are deleted outright — CLAUDE.md's "no
half-finished implementations" applies to removing a feature as much as adding one.

**8. Bootstrap script (`apps/web/scripts/create-admin.mjs`, `npm run db:create-admin`).**
With demo login gone and no public signup, *something* has to create the very first
account — otherwise nobody could log in to review the very first access request. This
idempotent, standalone script (mirrors `scripts/db-migrate.mjs`'s shape: loads its own env,
talks to Postgres directly) creates one `owner` user + organization from CLI flags or env
vars. This is an ops bootstrap step, not a UI feature — it is the one deliberate exception
to "no public signup, no demo accounts," and it is documented, not hidden.

## Consequences

**Positive**
- Demo access is fully removed: no shared password, no hardcoded account list, no public
  signup. Every account traces to a specific, admin-approved `AccessRequest` (or the one
  bootstrap admin) — an auditor can reconstruct who approved whom and when
  (`reviewed_by`/`reviewed_at`).
- Zero changes to RAG, the Knowledge Worker, or the Regulations ingestion/review pipeline
  — verified: `packages/rag`, `packages/knowledge-worker`, `packages/regulation-ingestion*`,
  and every KI-P6/KI-P7 file are untouched by this change.
- Invitation tokens are never stored in plaintext (sha256 only), one-time use is enforced
  under concurrency (`FOR UPDATE`), and expiry is enforced on every read, not just at
  creation.
- New integration test (`tests/eval/accessOnboarding.eval.ts`, wired into `npm test`)
  exercises the real flow against live Postgres end to end: request creation (incl.
  idempotent re-submission), approval creating a working invite, token preview, account
  creation with a hashed password, token-reuse rejection, expired-token rejection, and the
  reject path — cleans up every row it creates.

**Negative / costs — named, not hidden**
- **No email integration.** Approving a request surfaces the invite link in the admin UI
  for manual copy/send; there is no outbound email provider wired up. This is the natural
  next increment once a transactional-email provider is chosen, and is explicitly out of
  this phase's Authentication/Users/Organizations/Invitations/Access-Requests scope.
- **New web users cannot yet call `apps/api`.** `apps/api`'s `API_AUTH_TOKENS` is still a
  static, env-configured map from a handful of dev bearer tokens to backend `Principal`s
  (`apps/api/.../composition.py`) — it has no concept of a dynamically-created web user.
  Invited users get a syntactically-valid but functionally inert `apiToken`
  (`web-user:<id>`), so Policy Intelligence, Regulation Review, and the AI Worker Control
  Center — all of which proxy through `apps/api` using `ActorContext.apiToken` — will
  401/502 for every organization created through this flow until a real web-session-to-
  backend-principal bridge is built. That bridge is a backend-auth architecture decision
  in its own right and is out of KI-P9's explicit scope (auth/users/orgs/invitations
  only); named here rather than silently swept under the rug, the same way ADR-0031 named
  ADR-0032's retrieval-priority gap.
- **`organizations.org_type`/`industry` are placeholder values (`"Unspecified"`) for
  orgs created via accept-invite**, since the access-request form deliberately only
  collects what CLAUDE.md's spec asked for (name, email, organization/company name, job
  title, optional reason) — an owner can edit these later via the organization's own
  settings, unchanged by this phase.

## Alternatives considered

- **Create the organization at approval time instead of accept time.** Rejected: an
  approved-but-never-accepted invite (the requester loses the link, the token expires
  before they act) would leave a permanent, zero-member organization row with no owner —
  clutter with no clean-up path. Creating it inside the same transaction as the user
  account means an organization only ever exists if someone actually joined it.
- **Let the admin pick from the full 7-role RBAC matrix on the approval form.** Rejected:
  the invited user is, by construction, the sole member of a brand-new organization, so
  the fine-grained roles (`compliance_manager`, `risk_manager`, `analyst`, `auditor`,
  `viewer`) mostly don't apply yet — there's no one else in the org to divide labor with.
  The 3-way `owner`/`admin`/`member` choice (mapping `member` → `analyst`) matches the
  spec's literal ask and keeps the form simple; the org's owner can promote/adjust roles
  for teammates later via the (unmodified) organization membership machinery once more
  people join.
- **Store the raw invite token instead of its hash.** Rejected on the same reasoning as
  password storage: a database dump should not hand out usable credentials. Hashing costs
  nothing extra (tokens are already high-entropy random, not user-chosen, so no salt or
  slow KDF is needed — a fast sha256 is sufficient and avoids adding scrypt latency to a
  page-load-time token lookup).
- **Send invitations by email in this phase.** Rejected as scope creep: no email provider
  is wired up anywhere in the codebase today, and choosing/integrating one is a separate,
  properly-sized decision. Surfacing the link in the admin UI for manual send is the
  smallest correct increment; named as a follow-up rather than blocking this phase on it.
