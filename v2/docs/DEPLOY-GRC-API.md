# Deploying `grc-api`

**Audience:** someone who has never seen this repository and cannot ask whoever wrote it.
Everything needed is here. If you had to guess something, that is a bug in this document — fix it.

---

## 0. What you are deploying, in one minute

`grc-api` is a Python/FastAPI service. The Next.js web app (already on Vercel) calls it for the
whole Governance Program feature: the discovery interview, the AI-generated governance plan, and
plan execution. **The web app cannot do any of that on its own** — with `grc-api` missing, the
Governance Program page shows the interview and then fails when you try to start.

Three moving parts:

```
  Vercel (apps/web)  ──HTTPS──►  grc-api  ──►  PostgreSQL
                                    │
                                    └────────►  an LLM provider (OpenAI by default)
```

- **PostgreSQL** — one managed database is enough.
- **An LLM** — without it the API still starts and serves, but every governance plan is an
  echo of its input rather than a plan. This is logged loudly; see §7.
- The repository is a monorepo. Everything here lives under **`v2/`**.

---

## 1. Prerequisites

| you need | why |
|---|---|
| Docker (to build) | the image is the deployment unit |
| A container host | Railway, Render, Fly.io, Cloud Run, ECS — any of them |
| A PostgreSQL 14+ instance | the service's only datastore |
| An LLM API key | OpenAI by default; see §3 for alternatives |
| The web app's `GRC_API_SERVICE_SECRET` | must match exactly; see §3 |

No Python, no `uv`, no local database. The image contains everything.

**Sizing** (measured, not estimated): the image is **~784 MB**; the container uses **~75 MB RAM**
at rest and starts serving **~1 second** after the process launches. The smallest tier on any host
is enough. The *first* build takes roughly 1–2 minutes (longer with `--no-cache`) — it is not
hung.

---

## 2. Build the image

**The build context is `v2/`, not the app directory.** `grc-api` resolves about twenty sibling
packages through relative path dependencies, and a context rooted at the app cannot see them. This
is the single most common first mistake.

```bash
docker build -f apps/grc-api/Dockerfile -t rasheed-grc-api v2/
```

If your platform builds from the repository instead of a pre-built image, set:

- **Dockerfile path:** `v2/apps/grc-api/Dockerfile`
- **Build context / root directory:** `v2`

---

## 3. Environment variables

Names and shapes only. **Never commit a value.** Put them in the platform's secret manager.
The full annotated list is [`apps/grc-api/.env.example`](../apps/grc-api/.env.example).

### Required

| variable | shape | notes |
|---|---|---|
| `MISSION_STORE_DSN` | `postgresql://user:pass@host:5432/db` | missions, outbox, read models |
| `GOVERNANCE_STORE_DSN` | same | discovery sessions, governance plans |
| `GRC_API_SERVICE_SECRET` | opaque string | **must equal the web app's value byte for byte** |

`MISSION_STORE_DSN` and `GOVERNANCE_STORE_DSN` normally point at the *same* database. They are two
variables only so they *could* be split later. If either is unset, `DATABASE_URL` is used as a
fallback by the migrate command — but set them explicitly.

### Required for the plan to actually be written

| variable | shape | notes |
|---|---|---|
| `GRC_LLM_PROVIDER` | `openai` \| `claude` \| `gemini` \| `ollama` | defaults to `openai` |
| `OPENAI_API_KEY` | provider credential | read by the vendor SDK, never by this codebase |
| `GRC_LLM_MODEL` | optional | each adapter has its own default |

Switching provider is configuration, **but** the vendor SDK is an optional dependency: change
`"generation-engine[openai]"` in `apps/grc-api/pyproject.toml` to the matching extra and rebuild.

### Optional

`RETRIEVAL_PG_DSN` (a pgvector database — unrelated to this journey; migrations skip if unset) ·
`DB_POOL_MIN_SIZE` / `DB_POOL_MAX_SIZE` / `DB_POOL_TIMEOUT` · `PORT` (the platform usually sets it).

### On the Vercel side

| variable | value |
|---|---|
| `GRC_API_BASE_URL` | the deployed grc-api origin, e.g. `https://grc-api.example.com` — no trailing slash |
| `GRC_API_SERVICE_SECRET` | the same secret as above |

---

## 4. Deployment order

Order matters. Each step assumes the previous one succeeded.

1. **Provision PostgreSQL.** Note the connection string.
2. **Set every variable** from §3 on the service. Set the two Vercel ones too.
3. **Build and push the image** (§2).
4. **Run the release step — migrations.** Before any traffic:
   ```bash
   python -m grc_api.migrate
   ```
   Configure it as: Railway `releaseCommand` · Render `preDeployCommand` · Cloud Run a Job ·
   ECS a one-off task.

   > **Do not put this in the container's start command.** Every replica would run it against
   > every other on scale-out.

   Safe to re-run: the migrations are idempotent DDL. `--dry-run` lists without touching anything.
5. **Start the service.** Its command is already in the image; you do not need to supply one.
6. **Point the platform's probes** at §5.
7. **Redeploy the Vercel app** so it picks up the two new variables. Vercel does not apply
   environment changes to an existing deployment.

---

## 5. Health probes

| platform setting | endpoint | expected | why this one |
|---|---|---|---|
| liveness / restart | `/health` | `200 {"status":"ok"}` | no I/O — a slow database must never cause a restart loop |
| readiness / routing | `/health/ready` | `200 {"status":"ready"}` | checks connectivity **and** that migrations ran |
| startup (if separate) | `/health/startup` | `200 {"status":"ok"}` | connectivity only; gives a cold start room to breathe |

**Never point the restart policy at `/health/ready`.** During a database blip it would restart
every healthy container at the exact moment recovery needs them stable.

Verified behaviour (not aspirational — see §9):

- database unreachable → `/health/ready` returns **503** naming the error; `/health` stays 200
- database up but not migrated → **503** `missing table(s): missions — migrations not applied`

---

## 6. Verification order

Run these in order. Each one isolates a different failure, so stop at the first that fails and go
to §8.

```bash
BASE=https://your-grc-api-url

curl -sS $BASE/health           # 1. process is up
curl -sS $BASE/health/ready     # 2. database reachable AND migrated
curl -sS -o /dev/null -w '%{http_code}\n' $BASE/v1/missions   # 3. expect 401, NOT 500
```

3 returning **401** is success: routing and auth work, and you simply have no credentials. A
**500** means the app is broken; a **404** means you have the wrong URL or path.

4. **Check the startup logs** for `llm_provider_unconfigured` or `execution_degraded`. Either one
   means the API is serving but **every governance plan will be an echo, not a plan.**
5. **In the web app:** open Governance Program, complete the interview, confirm the Report renders
   with a written summary. This is the first moment all three — API, database, LLM — must be right
   together. If the interview runs but the report fails, go to §8 #7.

---

## 7. Rollback

The service is stateless; the database is not. Roll them back separately.

**The service** — redeploy the previous image tag. That is the whole procedure. Nothing in the
container holds state, so a previous version starts cleanly.

**The database** — do *not* attempt to "roll back" migrations. There are no down-migrations, by
design: every migration is additive (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`), so
an older service version runs fine against a newer schema — it simply ignores what it does not
know about. This is what makes rolling the service back safe on its own.

If a migration itself failed halfway:

1. `python -m grc_api.migrate` again — it is idempotent and will complete the remaining files.
2. If it fails again, read the error: it names the exact `.sql` file. Fix forward.
3. Restore from the database's own point-in-time backup **only** for genuine data loss. That is a
   last resort, and it costs every write since the snapshot.

**Known gap, stated plainly:** there is no apply-tracking ledger. Nothing detects a migration file
that was edited *after* it was applied somewhere. Treat applied migrations as immutable and add a
new file instead.

---

## 8. The ten most likely failures

Ordered by how often they actually happen.

**1. Build fails: `No such file or directory: ../../packages/...`**
The build context is the app directory instead of `v2/`. → §2. Context must be `v2`.

**2. Every governance request returns 401**
`GRC_API_SERVICE_SECRET` differs between grc-api and Vercel — a trailing space or newline is
enough. → Re-paste both from one source. During rotation this side accepts a comma-separated list;
the web side signs with the *first* entry.

**3. `/health/ready` → 503 `missing table(s): ... migrations not applied`**
The release step never ran, or ran against a different database. → Run `python -m grc_api.migrate`
and confirm its DSN is the one the service uses.

**4. `/health/ready` → 503 with `OperationalError`**
The database is unreachable: wrong host/port, firewall, or the platform requires TLS. → Check the
detail field; it names the exact error. Many managed providers need `?sslmode=require` appended to
the DSN.

**5. The Governance Program page shows "Something went wrong"**
`GRC_API_SERVICE_SECRET` is unset **on Vercel**. → Set it and redeploy. (The page itself no longer
dies from this, but the feature cannot work.)

**6. The interview runs, then the report fails with "not valid JSON"**
No LLM configured, so the draft step echoed. → Look for `execution_degraded` in the logs, then set
`GRC_LLM_PROVIDER` and its key. This is the single most common "it deployed but does nothing"
cause.

**7. Logs show `llm_provider_unavailable: ... ModuleNotFoundError`**
The provider was switched without its SDK extra. → Change the `generation-engine[...]` extra in
`apps/grc-api/pyproject.toml` to match and rebuild.

**8. `Missing credentials` from the vendor SDK at boot**
`GRC_LLM_PROVIDER` is set but its key is not — or the key has a typo. → The service still starts;
the log names the exact variable expected.

**9. Container restarts in a loop while the database is slow**
The restart policy points at `/health/ready`. → Point it at `/health`. → §5.

**10. Port already in use / the wrong service answers**
Something else is bound to the same port, and probes hit *it* instead. Locally this is very easy
to do and produces baffling results — a health check that passes while the container is broken.
→ Confirm what is listening (`lsof -nP -iTCP:8000 -sTCP:LISTEN`) before trusting any probe result.

---

## 9. Verify it yourself locally first

You can prove the entire deployment shape on a laptop with Docker, before touching a platform.
[`docker-compose.yml`](../docker-compose.yml) models the real order: Postgres → migrate → API.

```bash
cd v2
docker compose up -d --build       # postgres, then migrate, then the api

# The API is not up the instant compose returns. Wait for it rather than curling once and
# concluding it is broken. While it starts you will briefly see "connection refused" or
# "Recv failure: Connection reset by peer" — both mean "not yet", not "failed".
until curl -fsS localhost:8000/health >/dev/null; do sleep 2; done

curl -sS localhost:8000/health         # {"status":"ok"}
curl -sS localhost:8000/health/ready   # {"status":"ready","checks":[{"name":"missions_db","ok":true}]}
curl -sS -o /dev/null -w '%{http_code}\n' localhost:8000/v1/missions   # 401 — correct

docker compose logs migrate        # the 7 migrations it applied
docker compose run --rm migrate    # prove idempotency: safe to run again
docker compose down -v             # stop and DELETE the volume, for a true from-zero rerun
```

**Inspecting the local database.** Compose publishes Postgres on host port **55432**, not 5432 —
deliberately, because a local Postgres already using 5432 is common and the clash looks exactly
like a broken image. To look inside:

```bash
docker compose exec postgres psql -U postgres -d rasheed_v2 -c '\dt'   # expect 9 tables
```

**If `docker compose up` fails to bind a port**, something else already owns 8000 or 55432. See
failure #10 — and note that a *partial* clash is worse than a full one: another service answering
on 8000 will pass your health checks while the container is untested.

This compose file is for verification only — it is not the production topology, and its Postgres
password is a local throwaway. Your LLM key is passed through from your shell if set, never
written to a file.

Everything in §5 was verified this way: image built with `--no-cache` from zero, migrations applied
to an empty volume and re-run twice, all three probes 200, and both failure modes reproduced —
database stopped, and schema dropped while the database stayed up.

---

## 10. What is deliberately not automated

Setting secrets. They are entered by a person into the platform's secret manager, per this
project's rule that no developer holds production secrets — which is also why nothing in this
codebase reads a provider key: each vendor SDK resolves its own from the environment.
