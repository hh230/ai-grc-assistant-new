# Deploying grc-api

The frontend is on Vercel; `grc-api` is not deployed anywhere yet. That is the whole reason the
Governance Program page cannot work in the preview: the web app calls `GRC_API_BASE_URL`, which
defaults to `http://localhost:8000`, and signs each call with `GRC_API_SERVICE_SECRET`, which is
unset there.

Everything below is verified on this machine — image built, migrations applied to an empty
database, container reporting healthy — except the parts that require account credentials, which
are yours to enter.

## What is already done

| | status |
|---|---|
| `Dockerfile` (portable — Railway / Render / Fly / Cloud Run / ECS) | built and run |
| `python -m grc_api.migrate` — all 7 core migrations, idempotent | applied to an empty DB, twice |
| Health probes `/health`, `/health/startup`, `/health/ready` | all 200 in-container |
| Real executor + LLM provider selection | end-to-end verified (commit `f5c24eb`) |

## 1. Build

The build context is **`v2/`**, not `apps/grc-api/` — the app resolves ~20 sibling packages
through `[tool.uv.sources]` path entries, and a context rooted at the app cannot see them.

```bash
docker build -f apps/grc-api/Dockerfile -t rasheed-grc-api v2/
```

## 2. Provision Postgres

One managed Postgres is enough. `RETRIEVAL_PG_DSN` (pgvector) is optional and unrelated to the
Discovery → Plan journey.

## 3. Set the variables

Names, shapes and purposes are in [`apps/grc-api/.env.example`](../apps/grc-api/.env.example).
Set them in the platform's own secret store — not in this repository, and not on a developer
machine.

The two that must match **byte for byte** on both sides:

| variable | on grc-api | on Vercel (apps/web) |
|---|---|---|
| `GRC_API_SERVICE_SECRET` | accepts (comma-separated during rotation) | signs with the first entry |
| `GRC_API_BASE_URL` | — | the deployed grc-api URL, e.g. `https://grc-api.example.com` |

A mismatch is not subtle: every governance request 401s.

## 4. Release step — migrations

Run **once per deploy**, before traffic. Not on container start: every replica would race every
other on scale-out.

```bash
python -m grc_api.migrate
```

- Railway: `releaseCommand` · Render: `preDeployCommand` · Cloud Run: a Job
- Idempotent DDL (ADR 0045), so re-running is safe. `--dry-run` lists without touching anything.
- **Known gap:** no apply-tracking ledger, so nothing detects a migration edited after it was
  applied. Deliberate for now; tracked separately.

## 5. Probes

| platform setting | endpoint | why |
|---|---|---|
| restart / liveness | `/health` | process only — a slow database must not trigger a restart loop |
| readiness / traffic | `/health/ready` | checks Postgres; failing means "don't route to me yet" |
| startup (if separate) | `/health/startup` | same checks, for a longer initial grace period |

## 6. Verify the deployment, in this order

1. `GET /health` → `{"status":"ok"}`
2. `GET /health/ready` → `{"status":"ready", ...}` — proves the database is reachable **and
   migrated**
3. Check the boot log for `llm_provider_unconfigured` or `execution_degraded`. If either appears,
   the API is serving but **every governance plan will be an echo, not a plan.**
4. In the web app: open the Governance Program page, complete the interview, and confirm the
   Report renders — that is the first point where all three (API, database, LLM) must be right
   together.

## What is deliberately not automated

Setting secrets. They go into the platform's secret manager by a human, per this project's own
rule that no developer holds production secrets — which is also why nothing here reads a key.
