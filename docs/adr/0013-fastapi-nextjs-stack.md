# ADR 0013: FastAPI (backend) + Next.js (frontend) stack

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §4, §18, §22; ADR 0002, 0016

## Context

The AI/back-end layer needs first-class Python (the LLM, embedding, agent, and data
ecosystems live there) with strong typing and async I/O. The frontend needs a modern,
server-rendered, workspace-first UX with excellent DX, localization, and RTL/Arabic
support. The two must share typed contracts.

## Decision

**Backend/AI:** Python + **FastAPI**, async-first, with **Pydantic** models validating
every boundary, dependency injection via `Depends` (db sessions, auth, tenancy, services),
and the repository pattern. The API is a thin interface layer that calls Tools/Services —
no business logic in route handlers.

**Frontend:** **Next.js (App Router) + TypeScript + React**, Server Components by default,
Client Components only when interactivity requires it; Tailwind + a component library with
centralized design tokens; **TanStack Query** for server state; explicit loading/empty/
error states; localization and RTL (Arabic) support. The frontend never talks to the
database — only to the API, using types shared via `packages/contracts`.

Both runtimes are pinned, linted, type-checked, and formatted under uniform CI gates.

## Consequences

**Positive**
- Best-fit ecosystems for each side; strong typing end to end.
- Shared contracts keep frontend and backend in lockstep (monorepo, ADR 0002).
- Server-first rendering supports the workspace-first, explainable UX.

**Negative / costs**
- Two language toolchains to maintain (accepted in ADR 0002).
- Contract generation/sync between Python and TypeScript needs tooling discipline.

## Alternatives considered

- **Single-language full-stack (e.g. all TypeScript).** Rejected: weakens the Python AI/
  data story that is central to this product.
- **Django/Flask instead of FastAPI.** Rejected: FastAPI's async + Pydantic boundary
  validation best fit our AI, structured-output, and performance needs.
