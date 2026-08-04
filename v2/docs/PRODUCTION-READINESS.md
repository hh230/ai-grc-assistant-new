# grc-api — Production Readiness

**Status: B1–B4 CLOSED and merged. Remaining gaps are listed below, each with an owner.**

The deploy is an execution step, not an experiment: every question has an answer, and every
capability has a status that is either verified or explicitly not.

---

## Production Readiness Matrix

Legend — ✅ built and verified · ⏳ decided, not yet built · ❌ not started · ⚠️ conditional · 👤 owner decision

### Correctness

| Capability | Status | Evidence / what remains |
|---|---|---|
| Outbox capture (atomic with state) | ✅ | `OutboxSink`, ADR 0043 |
| **Outbox relay (delivery)** | ✅ | `python -m grc_api.relay` — live drain proved **38 → 0** undelivered |
| Delivery-side consumer | ✅ | `StructuredLogPublisher` — one audit line per event: tenant, mission, trace |
| Blocked-outbox handling | ✅ | stops, logs CRITICAL with row id + event name, exits non-zero |
| Plan integrity (no dangling deps) | ✅ | fixed in `scheduler.py`; **1500/1500** organizations clean |

### Availability

| Capability | Status | Evidence / what remains |
|---|---|---|
| Liveness probe | ✅ | `/health` — does no I/O, by design |
| **Readiness probe (connectivity)** | ✅ | `/health/ready` — `SELECT 1` on every distinct DSN |
| **Readiness probe (schema)** | ✅ | verified against an un-migrated DB: *"missing table(s): missions, outbox"* |
| Startup probe | ✅ | `/health/startup` — connectivity only, so a cold start isn't judged as failing |
| **Connection pool** | ✅ | 40 concurrent borrowers → **peak 8 connections**, 0 errors |
| Pool liveness check | ✅ | `check_connection` — no dead connection handed out after a failover |
| Bounded pool wait | ✅ | `DB_POOL_TIMEOUT`, default 10s |
| Read-only DB → 503 + `Retry-After` | ❌ | §11 — today an unhandled bare 500 |
| Graceful shutdown (API) | ⏳ | the relay handles SIGTERM; the API relies on uvicorn's default |

### Security

| Capability | Status | Evidence / what remains |
|---|---|---|
| **Secret rotation, no downtime** | ✅ | proved Node→Python: both keys valid during overlap, old **revoked** after |
| Rotation is configuration-only | ✅ | comma-separated `GRC_API_SERVICE_SECRET` on both sides |
| Blank/whitespace secrets refused | ✅ | a defect caught by its own test — `"   "` had been accepted as a key |
| Constant-time verification | ✅ | no short-circuit; key count not observable from response timing |
| Secrets never logged | ✅ | absence + remediation logged, never the value |
| Secrets in a managed store, no developer copy | 👤 | decision 4 — platform secret manager, least privilege, audit log |
| TLS to Postgres (`sslmode=require`) | ⏳ | part of the DSN set at deploy time |
| Private networking (DB not public) | ⏳ | platform configuration |
| Least-privilege runtime DB role | ⏳ | must differ from the migration role |

### Operability

| Capability | Status | Evidence / what remains |
|---|---|---|
| Structured JSON logs | ✅ | relay + health; request-level logging still to add |
| Audit trail outside the database | ✅ | the relay's `stream: "audit"` lines |
| Metrics (mission duration, outbox depth) | ❌ | §6 — outbox depth is the alert that keeps B1 from recurring silently |
| Alerting | ❌ | §6 — readiness, 5xx rate, outbox depth, connection count, disk |
| Error tracking | ⏳ | Sentry exists for `apps/web`; add grc-api under a `service` tag |
| Dockerfile | ❌ | none exists for grc-api today |
| One-command migrate | ❌ | seven manual `psql -f` today |
| **Migration ledger** | 👤 | decision 5: **approved** — amends ADR 0045, see below |

### Resilience

| Capability | Status | Evidence / what remains |
|---|---|---|
| Frontend degrades when the API is down | ✅ | fail-open reads; `/discovery` and `/plan` show an empty state, not an error |
| Missions resumable / idempotent | ✅ | CLAUDE.md §8; a re-launch is a no-op on a running mission |
| Backups + PITR | ⏳ | platform feature; **retention deferred** by decision 3 |
| **Restore rehearsed** | ❌ | a backup never restored is not a backup — the measured restore time *is* the RTO |
| Rollback (service) | ✅ | stateless; redeploy the previous digest |
| Rollback (schema) | ⚠️ | no `down` scripts — safe **only** under the backward-compatibility rule (§8) |
| Disaster-recovery runbook | ❌ | not written |

### Scale

| Capability | Status | Evidence / what remains |
|---|---|---|
| Horizontal scaling | ⏳ | stateless; start at 2 instances × 2 workers and size from measurement |
| **Mission execution mode** | ⚠️ | **inline — stated explicitly below** |

---

## Mission execution: the mode is declared, not discovered

Per the owner's ruling, B5 is **not a blocker** — but it must be explicit rather than found out:

> **Current mode:** `INLINE` — a mission executes inside the request that launches it.
> **Supported:** small deployments. `W` workers ⇒ at most `W` concurrent missions.
> **Future:** a queue/worker behind `MissionLaunchPort` — ADR 0055's deferred decision. The seam
> already exists, so this needs no change to any command.
> **Trigger to build it:** mission duration × concurrency approaching worker capacity. That is why
> mission-duration metrics (§6) are required rather than optional: without them this threshold is
> crossed silently.

---

## Owner decisions — recorded

| # | Decision | Ruling |
|---|---|---|
| 1 | Hosting region | KSA/Gulf, chosen for **data residency**, not latency. Platform still to select. |
| 2 | Outbox | **Fix it. No deploy without it.** → done |
| 3 | Backup retention | **Deferred** until the formal compliance policy exists |
| 4 | Production secrets | **No developer holds them.** Platform secret manager, least privilege, audit log |
| 5 | Migration ledger | **Approved** — "بعد سنة لن تتذكر: هل هذه القاعدة على Migration 31 أو 34؟" |

**Decision 5 amends ADR 0045**, which chose idempotent DDL with *no* apply-tracking ledger. I have
not edited that ADR: amending an accepted architectural decision is not something I do on my own.
The ledger stays ❌ above until the ADR is amended and it is built.

---

## Order of work

| | Step | Status |
|---|---|---|
| 1 | Outbox relay (B1) | ✅ |
| 2 | Real health checks (B2) | ✅ |
| 3 | Connection pool (B3) | ✅ |
| 4 | Secret rotation (B4) | ✅ |
| 5 | This matrix | ✅ |
| 6 | Hosting platform decision | 👤 |
| 7 | Dockerfile · migrate command · read-only→503 · request logging | ⬜ |
| 8 | Deploy to **staging** | ⬜ |
| 9 | Run the AI Harness against staging (`--team --http --browser`) | ⬜ |
| 10 | **Only after the harness passes on staging** → production | ⬜ |

Step 9 is why the harness exists: the first thing a new environment faces is the sweep, and the
sweep already refuses to call an unreachable environment a pass.

---

## 0. What we are deploying, precisely

`v2/apps/grc-api` — a FastAPI **composition root** (ADR 0052). It wires auth, tenant context, read
models, the Mission Engine/Runtime and the Tool Registry. No business logic lives in it.

Four properties of the existing code dominate every decision that follows:

| Property | Evidence | Consequence |
|---|---|---|
| **The core is synchronous** | ADR 0045/0039; `psycopg` sync, in-process `EventBus` | Concurrency comes from processes/threads, not `async`. Worker count is the scaling dial. |
| **A connection is opened per operation** | `composition.py::_connect` → `psycopg.connect(...)` per call, no pool | Postgres connection limits, not CPU, are the first ceiling. |
| **Mission execution runs inside the request** | `launch.py::DurableMissionLaunch.launch` drives the engine in-process | A long mission occupies a worker for its whole duration. |
| **Migrations have no runner and no ledger** | ADR 0045; `grc-api/README.md` §3 lists seven `psql -f` commands | Schema changes are a manual, ordered, human step. Nothing records what was applied. |

---

## Blockers — must be resolved before any production traffic

These are not polish. Each one is a defect that only becomes visible in production.

### B1 — The outbox is captured but never drained ⚠️ *most serious*

`OutboxRelay` exists in `mission-store`, and every mission write captures its events to the outbox
transactionally (ADR 0043). **Nothing in `grc-api` ever runs the relay** — `grep -rn "OutboxRelay"
grc_api/` returns nothing.

Today that is invisible, because the in-process `EventBus` delivers synchronously and no consumer
depends on the outbox. In production it means the outbox table **grows without bound** and the
at-least-once guarantee the ADR claims is not actually in force.

Two acceptable resolutions — this is a decision, not a default:
- **(a)** Run the relay as a separate process (same image, different command), draining on an
  interval. Correct, and the direction ADR 0043 points.
- **(b)** Deploy without the relay, and add a monitored alert on outbox row count plus a documented
  statement that outbox delivery is not yet live.

Deploying while *believing* (a) is in place when it is not is the only unacceptable option.

### B2 — No readiness probe

`/health` returns `{"status": "ok"}` without touching Postgres. It is a **liveness** probe only.

A process that is up but cannot reach its database will pass this check and be sent traffic, which
turns a database incident into a flood of 500s instead of a held rollout. A `/health/ready` that
executes `SELECT 1` against both DSNs is required before any load balancer is pointed at this
service.

### B3 — No connection pool

Every store operation calls `psycopg.connect()`. At *N* workers × concurrent requests, connection
count is unbounded from Postgres's point of view, and connection setup cost is paid per operation.

Managed Postgres offerings cap connections aggressively (often 20–100 on small tiers). This will be
the first thing to fall over under real load. `psycopg_pool.ConnectionPool` is the fix, introduced
behind the existing `_connect` seam — it is one function, which is why this is tractable.

### B4 — The signing secret cannot be rotated without downtime

`ServiceAssertionIdentityProvider.__init__` takes **one** secret. Rotation therefore requires both
`apps/web` and `grc-api` to change the value at the same instant; any skew rejects every request.

See §4 for the design that fixes this. It is a small change (accept a list, verify against each),
but it must exist *before* the first secret is ever set, because the first rotation is exactly when
you discover you cannot do it.

### B5 — Missions execute in the request path

A mission that takes 30 seconds holds a worker for 30 seconds. With `W` workers, `W` concurrent
missions exhaust the service and health checks begin to time out.

ADR 0055 explicitly defers the queue/worker decision behind `MissionLaunchPort` — the seam is
already there. Until it is implemented, the deployment must be sized for it (§9) and mission
duration must be measured (§6), not assumed.

---

## 1. Where does the Python service live?

**Not Vercel.** `apps/web` stays on Vercel; `grc-api` cannot follow it. Vercel's Python runtime is
serverless-function shaped: no long-lived process, execution time caps, and a new process per
invocation — which would multiply B3 (a fresh connection every request) and make B1 and B5
unsolvable, since neither a relay nor a worker can exist without a durable process.

**Recommendation: a container on a platform that runs long-lived processes** — Fly.io, Railway,
Render, or ECS/Cloud Run. The selection criteria that actually matter here:

1. Runs a persistent process (needed for the outbox relay and any future worker).
2. Postgres in the **same region** as the service — every request makes several round trips, so
   cross-region latency multiplies.
3. Private networking between service and database, so Postgres is never publicly reachable.
4. Supports a pre-deploy or one-off command (for migrations, §3).

**Region: choose to match data residency, not latency.** CLAUDE.md §20 requires regional data
handling, and the customer base is KSA-regulated (NCA ECC, SAMA, PDPL). This is a compliance
decision, and I am not making it: it belongs to whoever owns the customer commitments.

There is **no Dockerfile for grc-api** today (`apps/web/Dockerfile` exists; the API has none). It
needs one: `uv sync --frozen`, non-root user, and the run command from §9.

---

## 2. How does it connect to PostgreSQL?

Two environment variables, both already read by `composition.py`:

| Variable | Default | Purpose |
|---|---|---|
| `MISSION_STORE_DSN` | `postgresql://…/rasheed_v2` | missions, outbox, read models |
| `GOVERNANCE_STORE_DSN` | same | discovery, plans, org profiles |

They default to the same database deliberately, and the docstring says why: one setting means the
missions table and its read models "cannot drift into different databases". **Keep them equal in
production.** Splitting them is a decision with no current benefit and a real failure mode.

`rasheed_v2` is a *separate database* from V1's `aigrc`, which `apps/web` uses. Both must exist;
they are not interchangeable.

Requirements on the connection:
- `sslmode=require` at minimum in the DSN.
- Private networking; the database must not accept public connections.
- A dedicated role for the service with rights on `rasheed_v2` only — not a superuser, and not the
  role used to run migrations (§3).
- Pooling per B3.

---

## 3. Migrations

**Today: seven `psql -f` commands, in order, with no ledger recording what ran** (ADR 0045). Every
file is idempotent (`CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`), so re-running is
safe. That idempotency is what makes the current model survivable at all.

The README already records the consequence of skipping this step: routes return a bare
`500 Internal Server Error` from an unhandled `UndefinedTable`.

**Proposal — the minimum that makes this safe in production, without breaking ADR 0045:**

1. A single `migrate` command in the same image that applies every `.sql` file in a fixed, declared
   order. Same files, same idempotency — only the *invocation* becomes one reproducible command
   instead of seven manual ones.
2. It runs as a **pre-deploy step**, on the old code, before new instances start.
3. It uses a **migration role** distinct from the runtime role (DDL rights the app does not have).

**What I am explicitly not proposing:** adding a `schema_migrations` ledger. That contradicts
ADR 0045, which is an accepted architectural decision, and changing it is your call, not mine.
The gap it leaves is real and should be stated plainly: **without a ledger, nothing can tell you
whether a given database is up to date** — only that re-applying is harmless. The mitigation below
(§11) is a readiness check that fails when an expected table is missing.

---

## 4. Secret management and key rotation

**Secrets required:**

| Secret | Consumer | Notes |
|---|---|---|
| `GRC_API_SERVICE_SECRET` | both `apps/web` and `grc-api` | HMAC-SHA256 shared secret; identical on both sides |
| `MISSION_STORE_DSN` / `GOVERNANCE_STORE_DSN` | grc-api | contains the database password |
| LLM provider keys | grc-api | if the executor is wired to a real provider |

All come from the platform's secret store injected as environment variables — never files in the
image, never the repo. `apps/web` reads its copy from Vercel's encrypted env; `grc-api` reads its
copy from its platform's.

**Rotation, which the code cannot currently do (B4).**

The token is a short-lived assertion: `DEFAULT_TTL_SECONDS = 60`, minted fresh per request and
never cached. That property is what makes clean rotation possible — the fix is small:

1. Change the provider to accept **an ordered list of secrets**, verifying against each and
   accepting if any matches. Minting always uses the first.
2. Rotation then becomes: add the new secret as an *additional* accepted value on `grc-api` →
   deploy → switch `apps/web` to mint with the new one → deploy → remove the old value from
   `grc-api` → deploy.
3. Because tokens live 60 seconds, the overlap window need only exceed 60 seconds. There is no
   period in which valid requests are rejected.

Rotate on a schedule (quarterly is a reasonable default) and immediately on any suspected exposure.
The secret must never be logged: `service_identity.py` already states this, and the
`grc_api_service_secret_missing` log line deliberately logs the *absence* and remediation, never
the value.

---

## 5. Health checks

Three distinct checks, because they answer different questions:

| Endpoint | Question | Behaviour |
|---|---|---|
| `/health` *(exists)* | Is the process alive? | Returns `ok` without I/O. Never touches the DB — a DB outage must not cause a **restart loop**. |
| `/health/ready` *(to build, B2)* | Should it receive traffic? | `SELECT 1` on both DSNs, plus presence of one expected table per store. Fails → removed from rotation, not restarted. |
| `/health/startup` *(to build)* | Has it finished booting? | Passes once the first successful DB connection is made. Prevents a slow first connection from being read as a crash. |

The distinction between liveness and readiness is the one that matters most: **conflating them turns
a database incident into a restart storm**, which makes recovery slower precisely when the system is
already degraded.

Readiness must check for a required table, not just connectivity — that is the only automated
defence against the missing-migration failure in §3.

---

## 6. Monitoring

CLAUDE.md §19 requires that every AI action be reconstructable, so monitoring here is a compliance
requirement, not only an operational one.

**Must be emitted:**

- **Structured JSON logs** with a trace id propagated across
  `interface → orchestrator → agent → tool → service`, plus `tenant_id` on every line. Never log
  the service secret, the DSN, or document content.
- **Per-request**: method, route, status, duration, tenant.
- **Mission metrics**: start/complete/fail counts, and **duration distribution** — this is the
  number that tells you when B5 becomes urgent.
- **Outbox depth** — the alert that makes B1 visible instead of silent.
- **Database**: connection count (against the tier's cap), slow queries, replication lag if a
  replica exists.
- **LLM calls**: model, prompt version, tokens, latency, cost (CLAUDE.md §22).

**Alerts worth waking someone for:** readiness failing across instances; 5xx rate above threshold;
outbox depth growing monotonically; connection count near the cap; disk above 75% (§12).

`apps/web` already reports to Sentry. `grc-api` should report to the same project with a distinct
`service` tag, so a single incident is visible as one story across both.

---

## 7. Backup

The database is the only durable state; the service is stateless. So: **backups are a Postgres
concern, entirely.**

- Automated daily snapshots plus point-in-time recovery (WAL). PITR matters more than snapshots
  here, because the failure this protects against — a bad migration or a wrong `UPDATE` — is
  discovered hours later.
- **Retention** must be set from the customer's regulatory obligation, not from a default. GRC
  audit trails are the product's core value (CLAUDE.md §19: "reconstructable for external audit
  indefinitely, subject to retention policy"). That policy is a decision for you.
- **A backup that has never been restored is not a backup.** A restore into a scratch database,
  performed on a schedule and timed, is what turns this from a checkbox into a capability. The
  measured restore time *is* the RTO.
- Backups contain customer compliance data: encrypted at rest, access-controlled, and subject to
  the same residency rule as the primary (§1).

---

## 8. Rollback

The service is stateless, so **rolling back the service is trivial: redeploy the previous image.**
Keep the previous image tagged and available; deploy by immutable digest so "the previous version"
is unambiguous.

**The schema is where rollback is genuinely hard**, and honesty matters more than reassurance here:

Because migrations are idempotent `CREATE ... IF NOT EXISTS` DDL with no ledger and **no `down`
scripts**, there is no automated schema rollback. That is a direct consequence of ADR 0045.

The discipline that makes this survivable — and it must be a rule, not a hope:

> **Every migration must be backward-compatible with the previous release.**
> Add columns, never rename or drop in the same release that uses them. A destructive change is
> split across two releases: release N stops using the column; release N+1 drops it.

Under that rule, a service rollback is always safe, because the old code still runs against the new
schema. Break the rule once and rollback stops being possible exactly when it is needed.

---

## 9. Scaling

The dial is **process count**, because the core is synchronous (§0).

- Run `uvicorn` with multiple workers (or multiple single-worker instances behind the platform's
  load balancer — preferable, since it also gives instance-level redundancy).
- Start at **2 instances × 2 workers**, and size from measurement, not guesswork: p95 request
  duration, mission duration distribution, and connection count.
- **The binding constraint will be Postgres connections, not CPU** (B3). Workers × pool size must
  stay under the tier's cap with headroom for migrations and human access.
- Scale on request latency and queue depth rather than CPU — a worker blocked on a mission is busy
  but not CPU-hot, so CPU-based autoscaling will under-provision precisely when it matters.
- **Vertical before horizontal for the database.** A read replica is not useful yet: read models
  are queried through the same sync path and there is no read/write split in the code.

---

## 10. What happens if the service falls over?

**Blast radius:** `apps/web` degrades rather than dies, and this is already implemented and proven:
`lib/planExecution/service.ts` treats an unreachable backend as `UpstreamError(unreachable=true)`
and **fails open for read-only reads** (`onUnreachable: "warn"`). `/discovery` and `/plan` render
an empty state instead of an error boundary. That behaviour was built and verified in this session.

What actually breaks: creating or advancing missions, running Discovery, generating or approving a
plan. All *writes* stop; the rest of the product keeps working.

**Recovery:** the platform restarts the process on liveness failure. Missions are resumable and
idempotent by design (CLAUDE.md §8), so a mission interrupted mid-execution can be re-driven —
that is what `MissionLaunchPort.launch` being idempotent on a re-launch is for.

**The known gap, stated plainly:** `launch.py` documents it itself — on autocommit, a step's state
and its event commit as two statements, so a crash *between* them can drop that one execution
event. The mission state remains correct; the audit event may be lost. In a product whose value is
auditability this is worth tracking, and it is owned by the boundary's implementation (ADR 0055),
not by the deployment.

---

## 11. What happens if the database becomes read-only?

This is the failure mode most systems handle worst, because it is not "down".

Postgres goes read-only on failover to a replica, on certain disk-full conditions, and when a
managed provider protects an over-quota instance. Reads succeed; writes raise
`psycopg.errors.ReadOnlySqlTransaction`.

**Current behaviour: unhandled.** That error propagates as a bare 500 with no useful body — the same
class of failure the README already documents for missing tables. `apps/web` would show a generic
error, and nothing would indicate the cause.

**Proposal:**

1. Map read-only errors to **503 Service Unavailable** with `Retry-After`, not 500. A 503 says
   "try again"; a 500 says "this is broken", and the difference changes what both the client and
   the on-call human do.
2. **Readiness must fail** while the database is read-only — the instance genuinely cannot serve
   its purpose, so it should leave rotation rather than accumulate failures.
3. Reads continue to work, so the product degrades to read-only rather than dying. Given
   fail-open reads (§10), users can still *see* their plans and controls; they cannot change them.
   That is the correct degradation for a compliance product: **showing stale truth beats showing
   nothing, and refusing a write beats accepting one that will not persist.**
4. Alert immediately. A read-only database is nearly always a symptom of §12.

---

## 12. What happens if disk fills?

The most predictable outage in the list, and the one with the clearest early warning.

**What grows here, specifically:**

| Source | Growth | Bounded today? |
|---|---|---|
| **Outbox table** | every mission event | **No — nothing drains it (B1)** |
| `mission_events` / audit trail | every step, every mission | No — retention is a policy decision |
| Read model tables | with missions | No |
| WAL | with write volume | By provider config |
| Uploaded documents | with usage | Depends where they are stored |

The outbox is the standout: it is designed as a queue, and an undrained queue is an unbounded table.
**B1 is therefore not only a correctness bug; it is a disk-exhaustion clock.**

Disk full → Postgres goes read-only → §11. The two failures are the same incident, arriving in
sequence.

**Proposal:**
1. Alert at **75%** and page at **85%**, not at 95% — growth is monotonic here, so late warning
   leaves no room to act.
2. Fix B1, and monitor outbox depth as a first-class metric.
3. Decide an **audit-trail retention and archival policy**. This is a compliance decision (audit
   records must remain reconstructable — CLAUDE.md §19), so it is yours, not mine. The technical
   options are: keep indefinitely on a growing volume, or archive to object storage beyond N months
   with a documented restore path.
4. Store uploaded documents in object storage, not the database.

---

## Recommended order of work

Each step is independently verifiable, and none is a rewrite.

| # | Work | Why first |
|---|---|---|
| 1 | Decide **B1** (relay, or documented absence + alert) | Correctness and disk both depend on it |
| 2 | Multi-secret rotation support (**B4**) | Must exist before the first secret is set |
| 3 | Readiness/startup probes (**B2**), incl. required-table check | The only automated defence against §3 |
| 4 | Connection pool (**B3**) | First thing to fall over under load |
| 5 | Read-only + disk error mapping to 503 (§11) | Turns a mystery 500 into an actionable signal |
| 6 | Dockerfile + `migrate` command (§1, §3) | The deployable unit |
| 7 | Staging deploy, then the harness's `--http --browser` sweep against it | Proves it before production |
| 8 | Production deploy | An execution step by now |

Step 7 is the point of having built the harness: **the first thing a new environment should face is
the sweep**, and the sweep already refuses to call an unreachable environment a pass.

---

## Decisions I need from you

These are yours, not mine — each is a business or compliance choice, not an engineering one.

1. **Hosting platform and region** — driven by data residency (KSA/PDPL), not latency.
2. **B1**: run the relay, or deploy without it and accept a documented, monitored gap.
3. **Backup retention** and **audit-trail retention** — regulatory obligations, not defaults.
4. **Who holds production secrets**, and who may deploy.
5. Whether to add a migration ledger, which would amend **ADR 0045**.

I will not set production secrets, provision infrastructure, or deploy any service. When you have
made these calls, the work above is mechanical.
