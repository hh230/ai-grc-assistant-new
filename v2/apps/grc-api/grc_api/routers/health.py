"""Health probes — unauthenticated, outside `/v1`, no tenant required.

Three endpoints, because they answer three different questions and a load balancer acts on each
differently. Collapsing them is the classic operational mistake: **if liveness checks the database,
a database outage becomes a restart storm**, and the service spends the incident being killed and
restarted instead of waiting for its dependency to come back.

| endpoint          | question                   | failure means                          |
|-------------------|----------------------------|----------------------------------------|
| `/health`         | is the process alive?      | restart me                             |
| `/health/ready`   | should I receive traffic?  | take me out of rotation — do NOT kill  |
| `/health/startup` | have I finished booting?   | still starting; do not judge me yet    |

Readiness checks for a **required table**, not merely for connectivity. Migrations are applied by
hand with no ledger (ADR 0045), so "the database answers" and "the database has the schema this
build needs" are genuinely different facts — and the second is the one that has actually broken a
deployment here before (`grc-api/README.md` §3: a missing migration surfaces as an unhandled
`UndefinedTable` and a bare 500).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Response, status

logger = logging.getLogger("grc_api.health")

router = APIRouter()

# One table per store, chosen because each is created by that store's FIRST migration. If it is
# missing, none of that store's later migrations ran either — so this one cheap check stands in for
# "this database has been migrated for this build".
REQUIRED_TABLES: dict[str, str] = {
    "missions": "missions",
    "outbox": "outbox",
    "governance": "discovery_sessions",
}

# Bounded so a hung database cannot hold a probe open until the platform's own timeout fires — a
# probe that never answers is indistinguishable from a dead process, which would trip liveness.
PROBE_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name, "ok": self.ok}
        if self.detail:
            payload["detail"] = self.detail
        return payload


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness. Deliberately does NO I/O.

    The process is answering, therefore it is alive. It must not consult Postgres: a database
    outage would then be reported as "this process is broken", and the platform would restart
    healthy processes in a loop precisely when recovery needs them stable.
    """
    return {"status": "ok"}


@router.get("/health/startup")
def startup(response: Response) -> dict[str, Any]:
    """Startup. Passes once the database has answered at least once.

    Separate from readiness so a slow first connection reads as "still booting" rather than
    "failing", which is what stops a cold start from being killed before it can serve.
    """
    checks = _check_dependencies(require_schema=False)
    healthy = all(check.ok for check in checks)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "starting", "checks": [c.as_dict() for c in checks]}


@router.get("/health/ready")
def ready(response: Response) -> dict[str, Any]:
    """Readiness. Fails → remove from rotation; it must never cause a restart.

    Checks connectivity AND that a required table exists, because an un-migrated database answers
    `SELECT 1` perfectly while every real route returns 500.
    """
    checks = _check_dependencies(require_schema=True)
    healthy = all(check.ok for check in checks)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning(
            "readiness_failed", extra={"failed": [c.name for c in checks if not c.ok]}
        )
    return {"status": "ready" if healthy else "not_ready", "checks": [c.as_dict() for c in checks]}


def _check_dependencies(*, require_schema: bool) -> list[DependencyStatus]:
    """Probe every database this service cannot work without.

    Both DSNs are checked even though they default to the same database, because they are
    independently overridable — assuming they are equal is exactly how a split configuration goes
    unnoticed until a route fails.
    """
    from grc_api.composition import database_dsn, governance_database_dsn

    targets = [
        ("missions_db", database_dsn(), ["missions", "outbox"]),
        ("governance_db", governance_database_dsn(), ["governance"]),
    ]
    seen: set[str] = set()
    checks: list[DependencyStatus] = []

    for name, dsn, table_keys in targets:
        # The same DSN twice is one database; probing it twice would double the cost of every probe
        # and report one outage as two.
        if dsn in seen:
            continue
        seen.add(dsn)
        checks.append(_probe(name, dsn, table_keys if require_schema else []))

    return checks


def _probe(name: str, dsn: str, table_keys: list[str]) -> DependencyStatus:
    import psycopg

    try:
        with psycopg.connect(dsn, connect_timeout=PROBE_TIMEOUT_SECONDS) as connection:
            connection.execute("SELECT 1")
            missing = [
                REQUIRED_TABLES[key]
                for key in table_keys
                if not _table_exists(connection, REQUIRED_TABLES[key])
            ]
        if missing:
            # The failure the README documents: the database is fine, the schema is not.
            return DependencyStatus(
                name=name,
                ok=False,
                detail=f"missing table(s): {', '.join(missing)} — migrations not applied",
            )
        return DependencyStatus(name=name, ok=True)
    except Exception as exc:  # noqa: BLE001 — unreachable, auth, timeout, read-only
        # The DSN carries a password; only the exception type and message are safe to surface.
        return DependencyStatus(name=name, ok=False, detail=f"{type(exc).__name__}: {exc}")


def _table_exists(connection: Any, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %(table)s",
        {"table": table},
    ).fetchone()
    return row is not None
