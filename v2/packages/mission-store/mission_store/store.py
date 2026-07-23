"""`PostgresMissionStore` — the durable `MissionStorePort` (ADR 0043, Slice 1).

A **drop-in replacement** for `InMemoryMissionStore`: it implements the exact same
`MissionStorePort` contract (`save` / `get` / `find_by_idempotency_key`), so the Mission Engine
runs unchanged and never learns that missions now live in PostgreSQL — the payoff of defining the
port first (ADR 0042 §12.3).

Slice 1 scope (see the package README for the full in/out list):
- the three port methods, over a state-snapshot row (ADR 0043 §5), JSONB for nested collections;
- tenant isolation enforced **in SQL**; a cross-tenant overwrite is refused, not applied;
- a store-managed `revision` counter incremented on every write (present, **not enforced** — OCC
  is deferred, ADR 0043 §10 / assumption 2).

Idempotency collisions are surfaced as a typed `IdempotencyConflict` (Slice 2): a `save` whose
`(tenant_id, idempotency_key)` duplicates a *different* mission is blocked by the partial unique
index, and the raw driver uniqueness violation is wrapped so callers never see a database
exception (ADR 0043 §9, §11).

Deferred to a later slice, deliberately: the transactional unit-of-work / outbox mode (an injected
connection here is a **test/embedding affordance only**, not a caller-managed transaction), and
enforced optimistic concurrency.

The psycopg driver is imported **lazily**, inside the methods that touch the database, so the
package (and the pure `codec`) import with no driver present — matching the Retrieval Engine's
pgvector adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pipeline_contracts import TenantContext

from mission_store.codec import COLUMNS, JSONB_COLUMNS, mission_from_row, mission_to_row
from mission_store.config import TABLE
from mission_store.config import dsn as default_dsn
from mission_store.errors import IdempotencyConflict, MissionStoreError

if TYPE_CHECKING:  # import only for type checkers; never required at runtime to import the module
    import psycopg
    from mission_engine import Mission

_MISSING_PG = (
    "PostgresMissionStore needs the 'psycopg' package. "
    "Install the optional extra: mission-store[postgres]"
)

_WRITE_COLUMNS: tuple[str, ...] = COLUMNS
_SELECT_LIST = ", ".join(COLUMNS)


def _load_pg() -> tuple[Any, Any, Any]:
    """Import the psycopg pieces lazily: the module, the JSONB adapter, and the dict row factory.
    Kept out of module import so the package loads without the driver."""
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise ImportError(_MISSING_PG) from exc
    return psycopg, Jsonb, dict_row


class PostgresMissionStore:
    def __init__(
        self,
        *,
        dsn: str | None = None,
        connection: psycopg.Connection | None = None,
        table: str = TABLE,
    ) -> None:
        self._table = table
        self._owns_conn = connection is None
        if connection is not None:
            # Injected connection: a test/embedding affordance in Slice 1 (the transactional
            # unit-of-work mode is a later slice). Used as-is; the store does not manage its
            # transaction.
            self._conn = connection
        else:
            psycopg, _, _ = _load_pg()
            # autocommit: each save/get is a single statement and must be durable on return — the
            # engine calls `save` after every lifecycle transition and expects it committed.
            self._conn = psycopg.connect(dsn or default_dsn(), autocommit=True)

    # --- MissionStorePort ---------------------------------------------------------------

    def save(self, mission: Mission) -> None:
        """Upsert the mission as its current state. On conflict (same `id`) update in place — but
        only within the same tenant: the `WHERE tenant_id = EXCLUDED.tenant_id` guard makes a
        cross-tenant overwrite a no-op, which we detect and reject (ADR 0040 §5). Each write bumps
        the store-managed `revision` and `row_updated_at`."""
        # jsonb: the psycopg JSONB adapter (a class used as a wrapper)
        psycopg, jsonb, _ = _load_pg()
        row = mission_to_row(mission)
        params = {
            col: (jsonb(row[col]) if col in JSONB_COLUMNS and row[col] is not None else row[col])
            for col in _WRITE_COLUMNS
        }
        assignments = ", ".join(f"{col} = EXCLUDED.{col}" for col in _WRITE_COLUMNS if col != "id")
        placeholders = ", ".join(f"%({col})s" for col in _WRITE_COLUMNS)
        sql = (
            f"INSERT INTO {self._table} ({', '.join(_WRITE_COLUMNS)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT (id) DO UPDATE SET {assignments}, "
            f"revision = {self._table}.revision + 1, row_updated_at = now() "
            f"WHERE {self._table}.tenant_id = EXCLUDED.tenant_id"
        )
        try:
            cur = self._conn.execute(sql, params)
        except psycopg.errors.UniqueViolation as exc:
            # A *different* mission already holds this (tenant_id, idempotency_key): the ON CONFLICT
            # clause targets (id), so a new id with a duplicate key is not absorbed — it trips the
            # partial unique index (schema.py). Wrap the raw driver error so a caller never sees a
            # psycopg exception for an idempotency collision (ADR 0043 §9, §11). Tenant scope is
            # unchanged — the key is unique *per tenant*, so this only fires within one tenant.
            raise IdempotencyConflict(
                tenant_id=mission.tenant_id,
                idempotency_key=mission.idempotency_key,
                mission_id=mission.id,
            ) from exc
        if cur.rowcount == 0:
            # The row exists but the tenant guard blocked the update: a cross-tenant overwrite.
            raise MissionStoreError(
                f"refused to overwrite mission {mission.id}: it belongs to a different tenant"
            )

    def get(self, mission_id: str, tenant: TenantContext) -> Mission | None:
        """Fetch a mission within the caller's tenant scope. The `tenant_id` predicate is in the
        SQL, so a mission owned by another tenant is not found — cross-tenant reads cannot happen
        (ADR 0040 §5)."""
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {_SELECT_LIST} FROM {self._table} "
            f"WHERE id = %(id)s AND tenant_id = %(tenant_id)s"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"id": mission_id, "tenant_id": tenant.tenant_id})
            row = cur.fetchone()
        return mission_from_row(row) if row is not None else None

    def find_by_idempotency_key(self, tenant: TenantContext, key: str) -> Mission | None:
        """Return the tenant's mission for an idempotency key, if one exists. An empty key is not
        an idempotency key (the engine uses `""` to mean "no key") and never matches."""
        if not key:
            return None
        _, _, dict_row = _load_pg()
        sql = (
            f"SELECT {_SELECT_LIST} FROM {self._table} "
            f"WHERE tenant_id = %(tenant_id)s AND idempotency_key = %(key)s LIMIT 1"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"tenant_id": tenant.tenant_id, "key": key})
            row = cur.fetchone()
        return mission_from_row(row) if row is not None else None

    # --- lifecycle ----------------------------------------------------------------------

    def close(self) -> None:
        """Close the connection only if this store opened it. An injected connection is the
        caller's to close."""
        if self._owns_conn:
            self._conn.close()
