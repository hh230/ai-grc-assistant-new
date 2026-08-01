# mission-read-model

The first **product-side read model** for Rasheed V2 — the backend of Execution Slice **S1
(Mission List)** and a Domain-Model §3 gap made real.

## Why it exists

The Missions View asks one question: *"which missions does this tenant have?"* The frozen Core
answers *get one mission* (`MissionStorePort.get`) but has **no list-by-tenant read**, and it never
persists two things the list row shows — the product's **Mission Type** and the **scope/title**.
The Core aggregate stores a free-text `goal`; "Mission Type" lives in the product's `MissionCatalog`
and never lands on the mission. (This is the first assumption Slice S1 surfaced.)

This package fills the gap as a **CQRS read model**: a projection built *beside* the Core, never
mutating a mission.

## What it is

- `MissionListItem` — one list row: `mission_id · tenant_id · mission_type · title · status ·
  created_at · updated_at`. `status` is a **snapshot**; the Mission stays the source of truth
  (ADR 0046 §6), and the detail view (S2) reads it live.
- `MissionPage` — a page of rows + `page · page_size · total · has_next`.
- `MissionListReadModel` (port) — `record(item)` (idempotent upsert by `mission_id`) and
  `list_missions(tenant, *, status, mission_type, query, page, page_size)`.
- `InMemoryMissionListReadModel` — the driver-free adapter (tests / local). A Postgres adapter
  behind the same port backs deployment.

## Guarantees

- **Tenant-scoped, fail-closed** (ADR 0040 §5): `list_missions` returns only the caller's tenant's
  rows — no parameter can widen the scope, so cross-tenant leakage is impossible by construction.
- **Newest-first**, deterministic ordering (ties broken by `created_at`, then `mission_id`).
- **Bounded pages** (default 50, max 200) — the list never serializes unbounded (Interaction
  Principle 10).

## Status

- ✅ In-memory adapter + full acceptance tests (`uv run pytest`, ruff, mypy --strict — all green).
- ✅ **Postgres adapter** (`PostgresMissionListReadModel`, same port; lazy psycopg; isolation in SQL;
  DDL in `schema.py`). Install the driver with the `postgres` extra; the DB-gated test auto-skips
  without a reachable Postgres.
- ✅ Consumed by `v2/apps/grc-api` (`GET /v1/missions`) and fed by `mission-projection` (ADR 0053).
- ⏳ Remaining in S1: the **Missions View** frontend, then verification + the Slice Retrospective.
