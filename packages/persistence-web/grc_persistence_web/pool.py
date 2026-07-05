"""The shared asyncpg connection pool — the one seam every adapter in this package connects
through. `DATABASE_URL` is shared with `apps/web`'s own `pg` pool (`apps/web/lib/db/pool.ts`),
so it must tolerate every form that pool already accepts even though asyncpg's DSN parser is
stricter:

- A SQLAlchemy-style `+driver` suffix (e.g. `postgresql+asyncpg://...`), which asyncpg's parser
  does not understand at all.
- A Prisma-style `?schema=public` query parameter. `pg` (and Postgres itself) silently accepts
  this as a harmless unknown parameter, but asyncpg forwards it to the server as a runtime GUC
  named "schema", which does not exist, and the connection is rejected outright
  (`UndefinedObjectError: unrecognized configuration parameter "schema"`) — confirmed against
  the repo's actual dev `DATABASE_URL`, not a hypothetical.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg

_DRIVER_SUFFIX = re.compile(r"^(postgres(?:ql)?)\+[a-zA-Z0-9_]+://")

# Query parameters that are meaningful to other Postgres clients (or Prisma-style tooling) but
# have no libpq/asyncpg equivalent and must be dropped rather than forwarded to the server.
_UNSUPPORTED_QUERY_PARAMS = {"schema"}


def normalize_dsn(database_url: str) -> str:
    """Make a `DATABASE_URL` shared with apps/web's `pg` pool safe for asyncpg."""
    without_driver_suffix = _DRIVER_SUFFIX.sub(r"\1://", database_url)
    parts = urlsplit(without_driver_suffix)
    if not parts.query:
        return without_driver_suffix
    kept = [(k, v) for k, v in parse_qsl(parts.query) if k not in _UNSUPPORTED_QUERY_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(kept)))


class Database:
    """A pooled connection to apps/web's PostgreSQL database."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, database_url: str, *, min_size: int = 1, max_size: int = 10) -> Database:
        pool = await asyncpg.create_pool(
            normalize_dsn(database_url), min_size=min_size, max_size=max_size
        )
        if pool is None:  # pragma: no cover - asyncpg only returns None when passed a closed loop
            raise RuntimeError("failed to create the PostgreSQL connection pool")
        return cls(pool)

    @property
    def pool(self) -> asyncpg.Pool:
        return self._pool

    async def close(self) -> None:
        await self._pool.close()
