"""Apply every V2 core migration to the configured database. The deployment's release step.

Until now the schema arrived by whatever happened to call an `ensure_*` helper first, which works
on a developer's machine and not at all on a fresh managed Postgres: the API boots, the first
request touches a table nobody created, and the failure looks like a code bug. A deployment needs
one command that puts the schema in a known state before traffic arrives.

Migrations are hand-written, idempotent DDL (ADR 0045) — `CREATE TABLE IF NOT EXISTS`,
`ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS` — so running all of them on every release
is safe and needs no apply-tracking ledger. That is a deliberate trade for now, and it has a real
cost worth naming: nothing here detects a migration that was edited after it was applied. Adding
the ledger is tracked separately; this command is what makes a deploy possible at all.

Two databases, deliberately separate:

  * **core**      — missions, outbox, read models, discovery sessions, governance plans.
                    `MISSION_STORE_DSN` / `GOVERNANCE_STORE_DSN` (or `DATABASE_URL`).
  * **retrieval** — `knowledge_vectors`, which needs the pgvector extension.
                    `RETRIEVAL_PG_DSN`. Skipped unless that variable is set, because the API's
                    Discovery → Plan journey does not read it and a deployment without a vector
                    database must still be able to migrate.

    python -m grc_api.migrate            # core (and retrieval, if RETRIEVAL_PG_DSN is set)
    python -m grc_api.migrate --dry-run  # list what would run, touch nothing
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

V2_ROOT = pathlib.Path(__file__).resolve().parents[3]
PACKAGES = V2_ROOT / "packages"

# Order matters within a package (0001 before 0002); across packages it does not, because no
# migration references another package's table.
CORE_MIGRATIONS: tuple[str, ...] = (
    "mission-store/migrations/0001_missions.sql",
    "mission-store/migrations/0002_outbox.sql",
    "mission-store/migrations/0003_approval.sql",
    "mission-read-model/migrations/0001_mission_read_model.sql",
    "governance-store/migrations/0001_organization_profiles.sql",
    "governance-store/migrations/0002_discovery.sql",
    "governance-store/migrations/0003_governance_plans.sql",
)

RETRIEVAL_MIGRATIONS: tuple[str, ...] = (
    "retrieval-engine/migrations/0001_knowledge_vectors.sql",
    "retrieval-engine/migrations/0002_tenancy_columns.sql",
)

CORE_DSN_ENV_VARS = ("MISSION_STORE_DSN", "GOVERNANCE_STORE_DSN", "DATABASE_URL")
RETRIEVAL_DSN_ENV_VAR = "RETRIEVAL_PG_DSN"


class MigrationError(RuntimeError):
    pass


def core_dsn(env: dict[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    for name in CORE_DSN_ENV_VARS:
        value = (source.get(name) or "").strip()
        if value:
            return value
    raise MigrationError(
        "No database configured. Set one of " + ", ".join(CORE_DSN_ENV_VARS) + "."
    )


def _resolve(relative: str) -> pathlib.Path:
    path = PACKAGES / relative
    if not path.is_file():
        raise MigrationError(f"migration missing from the image: {relative}")
    return path


def apply(dsn: str, relatives: tuple[str, ...], *, dry_run: bool = False) -> list[str]:
    """Apply each migration in order. Returns what ran (or would run)."""
    paths = [_resolve(relative) for relative in relatives]
    if dry_run:
        return [str(p.relative_to(PACKAGES)) for p in paths]

    import psycopg

    applied: list[str] = []
    # autocommit: each file is its own unit. A partially-applied file would otherwise roll back
    # silently and leave the operator believing the release succeeded.
    with psycopg.connect(dsn, autocommit=True) as conn:
        for path in paths:
            name = str(path.relative_to(PACKAGES))
            try:
                conn.execute(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001 — re-raised with the file that failed
                raise MigrationError(f"{name} failed: {type(exc).__name__}: {exc}") from exc
            applied.append(name)
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply V2 core migrations.")
    parser.add_argument("--dry-run", action="store_true", help="list migrations, change nothing")
    args = parser.parse_args(argv)

    try:
        dsn = core_dsn()
    except MigrationError as exc:
        print(f"migrate: {exc}", file=sys.stderr)
        return 2

    try:
        for name in apply(dsn, CORE_MIGRATIONS, dry_run=args.dry_run):
            print(f"{'would apply' if args.dry_run else 'applied'}: {name}")

        retrieval = (os.environ.get(RETRIEVAL_DSN_ENV_VAR) or "").strip()
        if retrieval:
            for name in apply(retrieval, RETRIEVAL_MIGRATIONS, dry_run=args.dry_run):
                print(f"{'would apply' if args.dry_run else 'applied'}: {name}")
        else:
            print(f"skipped retrieval migrations ({RETRIEVAL_DSN_ENV_VAR} not set)")
    except MigrationError as exc:
        print(f"migrate: {exc}", file=sys.stderr)
        return 1

    print("migrate: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
