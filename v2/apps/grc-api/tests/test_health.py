"""Tests for the health probes (B2).

The property that matters most is the SEPARATION: liveness must not depend on the database, or a
database outage turns into a restart storm and the service spends the incident being killed instead
of waiting for its dependency to return.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from grc_api.app import create_app
from grc_api.composition import Storage
from grc_api.routers import health


def _client() -> TestClient:
    return TestClient(create_app(storage=Storage.MEMORY))


# --- the separation that prevents a restart storm ---------------------------------------------


def test_liveness_never_touches_the_database(monkeypatch: Any) -> None:
    """If liveness consulted Postgres, an outage would be reported as "this process is broken" and
    the platform would restart healthy processes in a loop, precisely when recovery needs them
    stable."""

    def explode(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("liveness must not probe the database")

    monkeypatch.setattr(health, "_probe", explode)
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_fails_when_the_database_is_unreachable(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        health,
        "_probe",
        lambda name, dsn, keys: health.DependencyStatus(name, False, "OperationalError: refused"),
    )
    response = _client().get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_readiness_passes_when_dependencies_are_healthy(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        health, "_probe", lambda name, dsn, keys: health.DependencyStatus(name, True)
    )
    response = _client().get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


# --- the failure a connectivity check cannot see -----------------------------------------------


def test_readiness_requires_the_schema_not_merely_a_connection() -> None:
    """An un-migrated database answers SELECT 1 perfectly while every real route returns 500. That
    exact failure is documented in the README as the most common cause of a bare 500 on a fresh
    deployment, so readiness must check for a table, not just a connection."""
    assert "missions" in health.REQUIRED_TABLES.values()
    assert "outbox" in health.REQUIRED_TABLES.values()
    assert "discovery_sessions" in health.REQUIRED_TABLES.values()


def test_startup_does_not_require_the_schema(monkeypatch: Any) -> None:
    """Startup asks "can I reach the database", not "is it migrated" — so a cold start is not
    judged as failing before it can serve."""
    requested: list[list[str]] = []

    def record(name: str, dsn: str, keys: list[str]) -> health.DependencyStatus:
        requested.append(keys)
        return health.DependencyStatus(name, True)

    monkeypatch.setattr(health, "_probe", record)
    assert _client().get("/health/startup").status_code == 200
    assert all(keys == [] for keys in requested), "startup must not demand tables"


def test_a_missing_table_is_reported_with_a_remediation(monkeypatch: Any) -> None:
    """"not_ready" alone sends someone hunting. Naming the table points straight at the fix."""
    monkeypatch.setattr(
        health,
        "_probe",
        lambda name, dsn, keys: health.DependencyStatus(
            name, False, "missing table(s): missions — migrations not applied"
        ),
    )
    body = _client().get("/health/ready").json()
    assert "migrations not applied" in body["checks"][0]["detail"]


# --- not leaking, not double-counting ----------------------------------------------------------


def test_a_shared_dsn_is_probed_once(monkeypatch: Any) -> None:
    """Both DSNs default to the same database. Probing it twice would double every probe's cost
    and report one outage as two."""
    probed: list[str] = []
    monkeypatch.setattr(
        health,
        "_probe",
        lambda name, dsn, keys: (probed.append(dsn), health.DependencyStatus(name, True))[1],
    )
    monkeypatch.setattr("grc_api.composition.database_dsn", lambda: "postgresql://same")
    monkeypatch.setattr("grc_api.composition.governance_database_dsn", lambda: "postgresql://same")

    _client().get("/health/ready")
    assert len(probed) == 1


def test_both_databases_are_probed_when_they_differ(monkeypatch: Any) -> None:
    """They are independently overridable, so assuming they are equal is how a split configuration
    goes unnoticed until a route fails."""
    probed: list[str] = []
    monkeypatch.setattr(
        health,
        "_probe",
        lambda name, dsn, keys: (probed.append(dsn), health.DependencyStatus(name, True))[1],
    )
    monkeypatch.setattr("grc_api.composition.database_dsn", lambda: "postgresql://a")
    monkeypatch.setattr("grc_api.composition.governance_database_dsn", lambda: "postgresql://b")

    _client().get("/health/ready")
    assert len(probed) == 2


def test_a_probe_is_time_bounded() -> None:
    """A probe that never answers is indistinguishable from a dead process, which would trip
    liveness and restart a service whose only problem is a slow database."""
    assert 0 < health.PROBE_TIMEOUT_SECONDS <= 10


# --- pooling (B3) -------------------------------------------------------------------------------


def test_closing_a_pooled_connection_returns_it_instead_of_destroying_it() -> None:
    """Every call site says `finally: connection.close()`. Redefining close to mean "give it back"
    is what makes pooling work without rewriting — and risking — transaction handling at each one."""
    from grc_api.composition import _PooledConnection

    class _Pool:
        def __init__(self) -> None:
            self.returned: list[object] = []

        def putconn(self, connection: object) -> None:
            self.returned.append(connection)

    pool, real = _Pool(), object()
    _PooledConnection(pool, real).close()
    assert pool.returned == [real], "close must return the connection to the pool"


def test_a_pooled_connection_delegates_everything_else() -> None:
    from grc_api.composition import _PooledConnection

    class _Real:
        autocommit = True

        def execute(self, sql: str) -> str:
            return f"ran {sql}"

    wrapped = _PooledConnection(object(), _Real())
    assert wrapped.autocommit is True, "UnitOfWork rejects autocommit connections by reading this"
    assert wrapped.execute("SELECT 1") == "ran SELECT 1"


def test_a_pooled_connection_refuses_to_be_used_as_a_context_manager() -> None:
    """psycopg's own __exit__ CLOSES the connection, which would defeat pooling. Dunder lookup
    skips __getattr__, so this raises loudly rather than quietly leaking one out of the pool."""
    import pytest

    from grc_api.composition import _PooledConnection

    with pytest.raises(TypeError):
        with _PooledConnection(object(), object()):
            pass


def test_the_pool_is_bounded_and_waits_are_not_unbounded() -> None:
    """A request queued forever on a pool is indistinguishable from a hung service, and it will
    trip a health probe."""
    from grc_api.composition import POOL_MAX_SIZE, POOL_TIMEOUT_SECONDS

    assert POOL_MAX_SIZE >= 1
    assert 0 < POOL_TIMEOUT_SECONDS <= 60
