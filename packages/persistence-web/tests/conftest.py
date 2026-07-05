"""Integration tests need a real Postgres with apps/web's migrations applied (the repo's
`docker/compose` `pgvector/pgvector:pg16` service, or any dev database with
`apps/web/scripts/db-migrate.mjs` already run against it) — a SQLite fake cannot stand in for
this schema. Point `TEST_DATABASE_URL` (or `DATABASE_URL`) at it; tests skip cleanly if neither
resolves to a reachable database.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from grc_persistence_web import Database

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _database_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if url:
        return url
    env_file = _REPO_ROOT / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


@pytest.fixture
async def database() -> AsyncIterator[Database]:
    url = _database_url()
    if not url:
        pytest.skip("no TEST_DATABASE_URL/DATABASE_URL configured")
    try:
        db = await Database.connect(url, min_size=1, max_size=2)
    except OSError as error:
        pytest.skip(f"database not reachable: {error}")
    try:
        yield db
    finally:
        await db.close()
