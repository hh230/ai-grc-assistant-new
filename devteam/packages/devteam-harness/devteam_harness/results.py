"""Result persistence — every scenario, every violation, in a real queryable database.

SQLite via stdlib `sqlite3`: a genuine database (indexed, queryable, transactional) with zero new
dependencies and no server to provision. That matters because the harness must run identically on
a laptop, in CI, and before a release. Postgres would have meant provisioning infrastructure to
find out whether the product works — the wrong trade for a tool whose job is to always be
runnable.

The schema stores the *seed* on every scenario, so any failure is reproducible with one command
rather than by hoarding fixtures.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    REAL    NOT NULL,
    finished_at   REAL,
    scenarios     INTEGER NOT NULL DEFAULT 0,
    passed        INTEGER NOT NULL DEFAULT 0,
    failed        INTEGER NOT NULL DEFAULT 0,
    start_seed    INTEGER NOT NULL,
    schema_version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS scenarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    seed        INTEGER NOT NULL,
    tenant_id   TEXT    NOT NULL,
    posture     TEXT    NOT NULL,
    concluded   INTEGER NOT NULL,
    ok          INTEGER NOT NULL,
    turn_count  INTEGER NOT NULL,
    error_type  TEXT,
    error       TEXT,
    -- The full question/answer transcript: what a human needs to understand a failure without
    -- re-running anything.
    transcript  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS violations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id),
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    seed        INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    detail      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scenarios_run ON scenarios(run_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_ok  ON scenarios(run_id, ok);
CREATE INDEX IF NOT EXISTS idx_violations_name ON violations(run_id, name);
"""


@dataclass(frozen=True)
class RunSummary:
    run_id: int
    scenarios: int
    passed: int
    failed: int
    violations_by_name: dict[str, int]

    @property
    def ok(self) -> bool:
        return self.failed == 0


class ResultStore:
    """Append-only store for harness runs. Safe to point at a file or `:memory:`."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path))
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(_SCHEMA)
        self._connection.commit()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._connection
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def start_run(self, *, started_at: float, start_seed: int) -> int:
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (started_at, start_seed, schema_version) VALUES (?, ?, ?)",
                (started_at, start_seed, SCHEMA_VERSION),
            )
        run_id = cursor.lastrowid
        assert run_id is not None
        return run_id

    def record_scenario(
        self,
        *,
        run_id: int,
        seed: int,
        tenant_id: str,
        posture: str,
        concluded: bool,
        ok: bool,
        turn_count: int,
        error_type: str | None,
        error: str | None,
        transcript: list[dict[str, object]],
        violations: list[tuple[str, str]],
    ) -> int:
        with self._tx() as conn:
            cursor = conn.execute(
                """INSERT INTO scenarios
                   (run_id, seed, tenant_id, posture, concluded, ok, turn_count,
                    error_type, error, transcript)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    seed,
                    tenant_id,
                    posture,
                    int(concluded),
                    int(ok),
                    turn_count,
                    error_type,
                    error,
                    json.dumps(transcript),
                ),
            )
            scenario_id = cursor.lastrowid
            assert scenario_id is not None
            conn.executemany(
                "INSERT INTO violations (scenario_id, run_id, seed, name, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                [(scenario_id, run_id, seed, name, detail) for name, detail in violations],
            )
        return scenario_id

    def finish_run(self, run_id: int, *, finished_at: float) -> RunSummary:
        with self._tx() as conn:
            conn.execute(
                """UPDATE runs SET
                     finished_at = ?,
                     scenarios = (SELECT COUNT(*) FROM scenarios WHERE run_id = ?),
                     passed    = (SELECT COUNT(*) FROM scenarios WHERE run_id = ? AND ok = 1),
                     failed    = (SELECT COUNT(*) FROM scenarios WHERE run_id = ? AND ok = 0)
                   WHERE id = ?""",
                (finished_at, run_id, run_id, run_id, run_id),
            )
        return self.summary(run_id)

    def summary(self, run_id: int) -> RunSummary:
        row = self._connection.execute(
            "SELECT scenarios, passed, failed FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        by_name = {
            r["name"]: r["n"]
            for r in self._connection.execute(
                "SELECT name, COUNT(*) AS n FROM violations WHERE run_id = ? "
                "GROUP BY name ORDER BY n DESC",
                (run_id,),
            )
        }
        return RunSummary(
            run_id=run_id,
            scenarios=row["scenarios"],
            passed=row["passed"],
            failed=row["failed"],
            violations_by_name=by_name,
        )

    def failing_seeds(self, run_id: int, *, name: str | None = None) -> list[int]:
        """The seeds needed to reproduce failures — the payoff of storing seeds at all."""
        if name is None:
            rows = self._connection.execute(
                "SELECT DISTINCT seed FROM scenarios WHERE run_id = ? AND ok = 0 ORDER BY seed",
                (run_id,),
            )
        else:
            rows = self._connection.execute(
                "SELECT DISTINCT seed FROM violations WHERE run_id = ? AND name = ? ORDER BY seed",
                (run_id, name),
            )
        return [r["seed"] for r in rows]

    def close(self) -> None:
        self._connection.close()
