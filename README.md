# AI GRC Assistant

A global, multi-tenant **Enterprise SaaS** platform that helps GRC teams author, map,
assess, and monitor controls, policies, and risks across many compliance frameworks —
grounded in the customer's own evidence and executed as governed **missions**.

> **Status (source-verified 2026-06-27).** The backend core is partially built along the
> Handbook's Knowledge-First roadmap: the **Domain**, **Application/Services**, and
> **Persistence** layers are implemented (20 DB tables + Alembic migration), and the
> **Knowledge Extraction Engine** has its port/abstraction layer. Test coverage so far is
> the knowledge + extraction domain and the persistence layer; the rest is implemented but
> not yet test-verified. The **AI stack** (orchestrator, agents, tools, RAG, framework
> engine) and the **API** are **not started**; `apps/web` is a **static presentation
> prototype** (hardcoded demo data, no backend wiring). Authoritative, evidence-based status
> lives in [`PROJECT_STATE.md`](./PROJECT_STATE.md) (the PSR) and
> [`docs/architecture/ARCHITECTURE_AUDIT.md`](./docs/architecture/ARCHITECTURE_AUDIT.md).

## Read first

- [`CLAUDE.md`](./CLAUDE.md) — the engineering constitution (architecture, principles, DoD).
- [`docs/architecture/PROJECT_SKELETON.md`](./docs/architecture/PROJECT_SKELETON.md) — the
  repository structure and how to extend it.

## Stack

Next.js (App Router, TypeScript) · FastAPI (Python) · PostgreSQL + pgvector · monorepo
(pnpm + turbo for JS, uv for Python).

## Layout

```
apps/        deployable units: web, api, orchestrator, workflow, worker
packages/    reusable capability: domain, services, tools, agents, rag, framework-engine, …
frameworks/  compliance frameworks as data (NCA ECC, SAMA, PDPL, ISO, NIST, CIS, COBIT, COSO)
prompts/     versioned prompt artifacts
docs/        architecture, ADRs, runbooks, onboarding
infra/       Infrastructure as Code
docker/      Dockerfiles & compose (Postgres + pgvector)
config/      configuration as data (no secrets)
scripts/     dev/ops automation
tests/       cross-cutting e2e, mission, and AI evaluation suites
```

## Getting started

```bash
cp .env.example .env
make bootstrap     # pnpm install + uv sync
make db-up         # start Postgres (pgvector) locally
```

Open `ai-grc-assistant.code-workspace` in VS Code and install the recommended extensions.

## Quality gates

`make lint` · `make typecheck` · `make test` · `make format` — enforced in CI
(`.github/workflows/ci.yml`). See [`CLAUDE.md` §24](./CLAUDE.md) for the Definition of Done.
