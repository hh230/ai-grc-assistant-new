# Knowledge Center (V2)

The operational dashboard for the Rasheed V2 Knowledge Pipeline. A **read-only
visualization layer** over the artifacts the pipeline generates (manifests, chunks,
embedding manifest, embedding index). It never reads PDFs or any live source, and it
holds no business logic in components — all aggregation lives in the services.

Next.js (App Router) + TypeScript, Server Components by default. V2-only; does not touch
V1 (`apps/web`).

## Run

```bash
cd v2/apps/knowledge-center
npm install
npm run dev      # http://localhost:3111
```

The app reads artifacts from `../../knowledge` by default; override with the
`KNOWLEDGE_DIR` environment variable.

```bash
npm run test        # vitest — service unit tests
npm run typecheck   # tsc --noEmit
npm run build       # production build
```

> Do not run `npm run build` while `npm run dev` is live — the two share `.next` and the
> production build will clobber the dev server's chunks (`Cannot find module './xxx.js'`).
> If that happens: stop the dev server, `rm -rf .next`, restart.

## Architecture

Strict separation — the requirement that "no business logic belongs in React
components":

- **`lib/types/`** — `artifacts.ts` (exact on-disk schema, snake_case) and `view.ts`
  (UI-shaped view models, camelCase). Components see only view models.
- **`lib/services/knowledgeRepository.ts`** — the *only* layer that touches the
  filesystem. Reads the JSON artifacts, returns typed data, holds no logic.
- **`lib/services/libraryService.ts` · `documentService.ts` · `pipelineHistoryService.ts`**
  — pure aggregation functions (overview, rows, filter/search, document detail, run
  history). No I/O, so they are fully unit-tested without a running app or filesystem
  (`lib/services/services.test.ts`).
- **`components/`** — presentational only. `DocumentsExplorer` is the single interactive
  (client) component; its filter/search is delegated to the pure `filterDocuments`
  service — it holds selection state and renders, nothing more.
- **`app/`** — Server Components that load raw data via the repository, transform it via
  the services, and pass view models to components.

## Pages

- **`/`** — Knowledge Center: library overview (documents, pages, chunks, embeddings,
  profiles, last run, parse/chunk/embed success rates), the documents table with filters
  (category, profile, status, parser, language) + search (name / filename / category),
  and reconstructed pipeline history.
- **`/documents/[documentId]`** — Document detail: general info, pipeline status, parsing
  info, parser attempts, chunk statistics, embedding statistics, citation samples,
  warnings/failures, the raw manifest, and disabled Re-parse / Re-chunk / Re-embed
  buttons (prepared for a future phase).

## Scope

This phase is purely the operational dashboard. It does **not** implement a vector
database, search over embeddings, AI chat, or RAG — those are later phases.
