# grc-persistence-web

Adapters against **`apps/web`'s existing PostgreSQL schema** — the AI runtime's (`apps/api`,
`apps/worker`) only database. There is exactly one Postgres database in this platform; this
package does not create a second one, and it does not touch `packages/persistence`'s separate
SQLAlchemy schema (gated on ADL-0008 for unrelated reasons).

Migrations are authored and applied through `apps/web/lib/db/migrations/` and
`apps/web/scripts/db-migrate.mjs` — this package only reads/writes tables that already exist
there. If a Policy Intelligence feature needs new columns or tables, the migration goes in
`apps/web/lib/db/migrations/`, not here.

## Contents

- `pool.py` — an asyncpg connection pool behind a `Database` port; normalizes a SQLAlchemy-style
  `DATABASE_URL` (e.g. `postgresql+asyncpg://...`) to the plain `postgresql://` scheme asyncpg
  expects, since the same `DATABASE_URL` env var is shared with `apps/web`'s `pg`-based pool.
- `invocations.py` — `PostgresToolInvocationRecorder`, the concrete implementation of
  `grc_tools.ToolInvocationRecorder` against the `ai_tool_invocations` table.
- `policies.py` — `PolicyRepository`: read/list against `policies`, plus `insert_draft`, used by
  the Policy Builder Agent to write an AI-authored draft with its provenance columns
  (`ai_generated`, `generated_by_tool`, `generation_metadata`) populated. Never writes a
  `published` policy — the existing publish/approval workflow in `apps/web` is unchanged.
- `missions.py` — `PolicyMissionStore`: the lightweight Mission record (`policy_missions` +
  `policy_mission_steps`) for Policy Hunter/Analyst/Builder runs.

Every tenant-scoped query filters on `tenant_id` first (default deny — CLAUDE.md §20). Tests
require a live Postgres (the repo's `docker/compose` `pgvector/pgvector:pg16` service) with
`apps/web`'s migrations applied — a SQLite fake cannot faithfully stand in for
Postgres-specific behavior elsewhere in this schema (`pgvector`'s `<=>` operator).
