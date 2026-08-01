# ADR 0052: The V1 Product API Host — `v2/apps/grc-api`

- Status: **Accepted** (2026-07-22)
- Date: 2026-07-22
- Deciders: Product Owner (this decision reserved to the owner as the first post-freeze
  architectural call), Architecture
- Related: `REST_API_CONTRACT_V1.md` (the contract this host serves), `V1_EXECUTION_PLAN.md`
  (the enabling layer), `PRODUCT_DEVELOPMENT_PROCESS.md` (Architecture & Product Freeze), ADR 0046
  (AI GRC Assistant — the product layer), ADR 0042/0043/0044 (the frozen Core the host composes),
  `mission-read-model` (the first read model the host will expose).

---

## Context

The Product Design Foundation is frozen and implementation has begun (Slice S1, Mission List). The
first slice surfaced a question that is architectural, not behavioural: **what is the official
Product API Host for V1** — the process that hosts every endpoint in `REST_API_CONTRACT_V1.md`?

Two existing things are *not* it:

- **`apps/api` (`grc-app-api`) is the previous generation.** It depends on the old `packages/`
  (`grc-tools`, `grc-persistence-web`, `grc-policy-*`), uses a different `ToolRegistry`, cites the
  old ADR-0013, and is a scaffold ("no routers yet"). It references **no** `v2/packages`. The whole
  `apps/{api,orchestrator,web,worker,workflow}` + `packages/` tree is pre-V2.
- The V2 world is deliberately isolated under **`v2/`**: `v2/packages` (frozen Core + product
  layer), `v2/docs` (the Foundation), and **`v2/apps/` already exists** (it holds `knowledge-center`).

Building the new product API on `apps/api` would re-mix the two generations — exactly the drift the
Freeze rule exists to prevent. There is currently **no** V2 REST API host.

## Decision

Create the official V1 Product API Host at **`v2/apps/grc-api/`** (FastAPI).

- It is the **single surface** that hosts every command and query in `REST_API_CONTRACT_V1.md`.
- It is a **Composition Root only**: it wires Auth · Tenant Context · Read Models · Mission Engine /
  Runtime · Tool Registry · Routes, and shapes HTTP. **No business logic lives in the host** — that
  stays in `v2/packages/*` (Interfaces → … → Domain; the host is the outermost Interface ring).
- It lives under `v2/` (not `apps/`) so the generational boundary stays crisp and V2 remains
  self-contained; `v2/apps/` is the already-established home for V2 apps.
- Name `grc-api` matches the product's frozen positioning ("AI GRC Workspace"); it composes v2
  packages exclusively and never imports the old `packages/`.

## Consequences

- **Positive.** One derivation point for all endpoints; no generational mixing; the frozen Core is
  consumed unchanged; the old `apps/`/`packages/` tree is neither extended nor resurrected.
- **Follow-ups (not decided here).** How the host resolves **Auth + Tenant Context** in V1 (enabling
  layer item 2 — likely a dev bearer token → tenant in local, OIDC later; RBAC enforcement deferred
  with the guards kept declared in the contract). The **frontend host** is a *separate* decision
  (apps/web vs `v2/apps/web`), taken when S1 reaches its frontend step — deliberately not conflated
  here.
- **Scope discipline.** This ADR fixes *where the product API executes*, not *what any endpoint
  does* — behaviour stays derived from the frozen contract.
