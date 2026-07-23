# The Production Composition suite

**The safety net that had to exist before any Wave 1 wiring.**

Every other suite in this repository proves the **Development Composition** — the in-memory store,
the in-memory read models, `EchoExecutor`, and the seeded development identity. Wave 1 exists to
*replace* exactly those. So until this suite existed, a green test run said nothing at all about the
path we are about to build: the safety net measured the wrong thing.

This suite drives the API host over **real PostgreSQL**, and asserts the properties a deployment
depends on. It is deliberately **black-box**: every assertion goes through HTTP or through an
out-of-band SQL session, never through an internal seam. That way the later Wave 1 commits are free
to satisfy these tests however the design requires — the tests state the *target*, not the mechanism.

## What each file guards

| File | Guards |
|---|---|
| `test_durability.py` | Work survives the process. A mission, a list, and uploaded evidence all outlive the app instance that created them, and tenant isolation still holds when it is SQL enforcing it rather than a dictionary. |
| `test_transaction_boundary.py` | **ADR 0055.** A command's mission write, its events, and its projection commit **together**; and mission *execution* runs **outside** any transaction, so an already-recorded step is visible to another session before the mission finishes. |
| `test_production_defaults.py` | **The Wave 1 exit criterion**, expressed as a test: the default composition contains no Development Composition adapter. |

## Expected state when this suite first lands

Most of it **fails**, and that is the point — a safety net that passes before the work is done is
measuring nothing. Ordered by the Wave 1 sequence that makes each one pass:

- `test_durability.py` — **passes on arrival.** `create_app` already accepts injected adapters, so
  these prove the durable adapters work *through the host*. They are the baseline everything else is
  measured against.
- `test_transaction_boundary.py` — **fails**, except the execution guard. There is no outbox in the
  host's composition and no shared transaction across the three participants.
- `test_production_defaults.py` — **fails.** By construction: the defaults are still in-memory. This
  is the last test in Wave 1 to go green, and when it does, Wave 1 is over.

## Running it

```bash
cd v2/apps/grc-api && uv run pytest tests/production -v
```

The suite **skips cleanly** when no PostgreSQL is reachable, matching every other DB-gated suite in
`v2/`, so a database-free CI stays green. The DSN comes from `MISSION_STORE_DSN` (default: the
isolated `rasheed_v2` development database). Every test stands its own throwaway `*_pc_<suffix>`
tables up and drops them afterwards, so nothing touches the canonical tables.

`psycopg` and `mission-store` are **dev-only** dependencies of this app. The production
`dependencies` list stays untouched until the Wave 1 wiring commits land — this commit is tests only.
