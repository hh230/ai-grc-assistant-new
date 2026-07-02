# Sentinel GRC — Web Platform (`@grc/web`)

The enterprise workspace for the AI GRC Assistant: authentication, document intelligence,
an AI assistant, evidence management, governance, risk, and reporting. Built on **Next.js 15
(App Router) + React 19 + TypeScript + Tailwind**.

This document covers the frontend platform delivered across roadmap milestones **P2–P10**.
See the repo root `CLAUDE.md` (engineering constitution) and `PROJECT_STATE.md` for the
broader system.

---

## What's inside (P2–P10)

| Milestone | Area           | Highlights                                                                                                                              |
| --------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **P2**    | Authentication | httpOnly JWT sessions (`jose`), edge middleware route protection, RBAC mirroring the backend (7 roles), login/logout, access-denied     |
| **P3**    | Upload Center  | Drag-&-drop, per-file XHR progress, server-side validation (size + MIME + magic bytes), tenant-scoped storage, document repository      |
| **P4**    | Analysis       | Parse (PDF/DOCX) → chunk → embed → vector store → **OpenAI (gpt-5) assessment**; status polling; grounded findings + framework coverage |
| **P5**    | AI Chat (RAG)  | Retrieval over indexed docs, **streaming** answers with inline citations, conversation history, grounded (refuses to hallucinate)       |
| **P6**    | Evidence       | Repository with **version history**, tagging, control linkage, search; PDF/Word/image uploads                                           |
| **P7**    | Governance     | Frameworks + Controls + Policies; **coverage computed from evidence links**; policy approval workflow (publish = human gate)            |
| **P8**    | Risk           | 5×5 risk register, inherent + residual scoring, mitigation plans, ownership, workflow; **risk acceptance = human gate**                 |
| **P9**    | Reports        | Executive / Compliance / Risk reports; **PDF (pdf-lib)** and **Excel (exceljs)** export; live dashboard summaries                       |
| **P10**   | Production     | Production build, security headers, structured logging, standalone output, docs                                                         |

## Architecture

Layered and swappable, mirroring the backend's ports-and-adapters philosophy:

```
app/                 Next.js App Router
  (app)/             authenticated workspace (protected layout: requireSession + SessionProvider + QueryProvider + AppShell)
  login/             public auth
  api/               Route Handlers (Node runtime): auth, documents, analyses, chat, evidence,
                     controls, governance, policies, risks, reports
components/          UI by domain (auth, layout, upload, documents, analysis, chat, evidence,
                     governance, policies, risk, reports, providers, ui)
hooks/              TanStack Query hooks (server state)
lib/                domain + services (no React):
  auth/             roles, permissions (RBAC matrix), session (jose), password (scrypt), server helpers
  db/               PostgreSQL connection pool port + SQL migrations (lib/db/migrations)
  storage/          BlobStore port + filesystem adapter (uploaded file bytes; object storage in prod)
  documents/ analysis/ evidence/ policies/ risk/ chat/   repositories + services (tenant-scoped)
  ai/               EmbeddingProvider/ChatProvider ports + OpenAI adapter + local fallback
  frameworks/       frameworks-as-data catalog (ISO 27001 / NCA ECC / NIST CSF)
  governance/       coverage engine
  reports/          aggregation + PDF/XLSX renderers
  observability/    structured logger
middleware.ts        edge auth gate
```

**Every repository is tenant-scoped, RBAC-checked, and backed by PostgreSQL** (+ pgvector for
embeddings) behind a port — swap the adapter without touching a caller; **AI providers sit
behind ports** (OpenAI now, local fallback, others later).

## Database (PostgreSQL + pgvector)

Every repository (documents, evidence, analyses, document-chunk embeddings, conversations,
policies, risks) is backed by PostgreSQL via `lib/db/pool.ts` (`pg`); document-chunk
embeddings are stored as native `vector(3072)` columns (pgvector, OpenAI
`text-embedding-3-large`) and retrieved with the `<=>` cosine-distance operator — exact
search, no ANN index (pgvector caps indexed dimensions at 2000; see
`lib/db/migrations/0005_document_chunks.sql`). Object bytes (uploaded files, evidence
versions) stay on the filesystem `BlobStore` port — swap that adapter for S3/GCS separately
in production.

```bash
docker compose -f docker/compose/docker-compose.deps.yml up -d   # Postgres + pgvector
pnpm --filter @grc/web db:migrate                                # apply lib/db/migrations
```

## Running locally

```bash
pnpm install
cp apps/web/.env.example apps/web/.env.local   # set AUTH_SECRET + OPENAI_API_KEY + DATABASE_URL
pnpm --filter @grc/web db:migrate                # create the schema
pnpm --filter @grc/web dev                       # http://localhost:3000
```

**Demo accounts** (tenant "Acme Financial Group", password `GrcDemo!2026`):
`owner@`, `admin@`, `compliance@`, `risk@`, `analyst@`, `auditor@`, `viewer@acme.test`.

## Quality gates

```bash
pnpm --filter @grc/web typecheck   # tsc --noEmit
pnpm --filter @grc/web lint        # eslint
pnpm --filter @grc/web build       # production build (requires AUTH_SECRET)
pnpm format:check                  # prettier
```

## Production

- `output: "standalone"` — deploy the traced server bundle (see `Dockerfile`).
- Security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy,
  Permissions-Policy) are applied to every response in `next.config.mjs`.
- Set a strong `AUTH_SECRET` (the app throws at startup in production without one).
- Point `DATABASE_URL` at a managed PostgreSQL instance with the `vector` extension
  available, and run `pnpm --filter @grc/web db:migrate` as part of deploy.
- Point `STORAGE_DIR` at a persistent volume, or swap the `BlobStore` adapter for S3/GCS.
- Structured JSON logs (`lib/observability/logger.ts`) are ready for any aggregator.

See `SECURITY.md` for the security posture.
