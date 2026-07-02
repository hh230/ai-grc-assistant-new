# ADR 0002: Monorepo strategy

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §4, §6; PROJECT_SKELETON §2

## Context

The AI GRC Assistant is a single product made of tightly-coupled parts in two runtimes:
a TypeScript frontend (Next.js) and a Python backend/AI layer (FastAPI, Orchestrator,
agents, tools). These parts share contracts — API schemas, domain vocabulary, event
shapes — that must evolve together. We need a repository strategy that keeps those
contracts consistent, enforces the inward-pointing dependency rule, and applies one set
of quality gates across the whole platform, while still allowing each deployable unit to
scale and release independently.

## Decision

We use a **single polyglot monorepo** with two coordinated workspace managers:

- **pnpm + turbo** for the TypeScript workspace (`apps/web`, `packages/ui`,
  `packages/contracts`, `packages/i18n`).
- **uv** for the Python workspace (`apps/api|orchestrator|workflow|worker`, the Python
  `packages/*`).

Deployable units live in `apps/`; reusable capability lives in `packages/`. Dependencies
point inward (`apps → packages → domain`); the domain depends on nothing. A top-level
task runner (`Makefile` + `turbo`) provides uniform `lint`, `typecheck`, `test`, `format`,
and `build` across both runtimes.

## Consequences

**Positive**
- Cross-cutting changes (e.g. adding a Tool that touches registry, service, test, and UI)
  land in one reviewable PR with one CI run.
- One source of truth for contracts; the frontend and backend cannot silently diverge.
- Uniform standards and the dependency rule are enforceable because the whole build graph
  is visible.

**Negative / costs**
- Two package managers add tooling complexity; contributors need both toolchains.
- CI must be scoped/affected-aware to stay fast as the repo grows (turbo caching, path
  filters).
- Requires discipline (CODEOWNERS, lint rules) to prevent unwanted cross-layer imports.

## Alternatives considered

- **Polyrepo (separate repos per service).** Rejected: contract drift, multi-PR changes,
  and duplicated standards outweigh independent-repo benefits at our coupling level.
- **Single-language monorepo (force one runtime).** Rejected: Next.js is the right
  frontend and Python is the right AI/back-end runtime; forcing one would harm both.
