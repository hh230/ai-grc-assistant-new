# grc-api — Rasheed V1 Product API Host (ADR 0052)

The single FastAPI surface that serves `REST_API_CONTRACT_V1.md`. A **composition root only**: it
wires Auth, Tenant Context, read models, the Mission Engine/Runtime, and the Tool Registry, and
shapes HTTP — no business logic lives here (that stays in `v2/packages/*`).

## Clone → Install → Migrate → Run

### 1. Install

```bash
cd v2/apps/grc-api
uv sync
```

### 2. Provision Postgres

The durable composition (the production default — see `create_app`'s `storage: Storage.DURABLE`)
needs a reachable Postgres database. Every package below defaults to the same isolated V2 database,
`rasheed_v2` (never V1's `aigrc`):

```
postgresql://postgres:postgres@localhost:5432/rasheed_v2
```

Override with `MISSION_STORE_DSN` / `GOVERNANCE_STORE_DSN` (both independently overridable, but
default to the same DSN) if your local Postgres differs.

### 3. Migrate

There is **no automated migration runner today** (CLAUDE.md's V2 persistence model, ADR 0045:
hand-written `.sql` migrations applied as idempotent DDL — `CREATE ... IF NOT EXISTS`, no
apply-tracking ledger). Apply every package's migration files, in order, once per fresh database:

```bash
psql "$DSN" -f ../../packages/mission-store/migrations/0001_missions.sql
psql "$DSN" -f ../../packages/mission-store/migrations/0002_outbox.sql
psql "$DSN" -f ../../packages/mission-store/migrations/0003_approval.sql
psql "$DSN" -f ../../packages/mission-read-model/migrations/0001_mission_read_model.sql
psql "$DSN" -f ../../packages/governance-store/migrations/0001_organization_profiles.sql
psql "$DSN" -f ../../packages/governance-store/migrations/0002_discovery.sql
psql "$DSN" -f ../../packages/governance-store/migrations/0003_governance_plans.sql
```

(No `psql` client available? Any Postgres driver works — e.g.
`python3 -c "import psycopg; psycopg.connect('$DSN', autocommit=True).execute(open('<file>').read())"`
with `psycopg` installed, run once per file above, in the same order.)

Every file is idempotent (`CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`) — safe to
re-run. Skipping this step is the single most common cause of a fresh deployment's `/v1/missions`,
`/v1/discovery/*`, or `/v1/governance-plans/*` routes returning a bare `500 Internal Server Error`
with no useful body (an unhandled `UndefinedTable` from the driver) — see ADR 0066's revision
history for one instance of this.

### 4. Run

```bash
uv run uvicorn grc_api.app:create_app --factory --port 8000
```

`GET /health` should return `200`. By default the app talks to `apps/web` via the fixed dev
credential provider; to accept `apps/web`'s HMAC service-assertion tokens too (required for the
Governance Discovery/Planning UI — see ADR 0066 "Frontend integration"), also set:

```bash
export GRC_API_SERVICE_SECRET=<the same value apps/web/.env.local sets for GRC_API_SERVICE_SECRET>
```

**Note on Mission execution.** The production default `ExecutionPort` is still `EchoExecutor` — it
runs a Mission's steps but each step's output is a literal `"echo: <input>"`, not real tool/LLM
work. Replacing it with the real `ToolRegistry`-backed `RegistryExecutor` by default is separate,
already-tracked work (`tests/production/test_production_defaults.py`). Every route works correctly
today either way; only the *content* a Mission produces differs. `tests/production/
test_governance_plan_e2e.py` shows the exact wiring (`create_app(executor=...)`) to stand up a real
executor for local manual testing, backed by a deterministic fake `GenerationProvider` (no API key
required, no live LLM call).

## Tests

```bash
uv run pytest              # fast, no external services
uv run pytest tests/production   # DB-gated — needs steps 2-3 above completed first; auto-skips otherwise
```
