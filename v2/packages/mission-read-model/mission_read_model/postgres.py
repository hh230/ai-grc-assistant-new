"""`PostgresMissionListReadModel` — the durable adapter (ADR 0053), same port as the in-memory one.

A drop-in `MissionListReadModel`: the API host and the projector never learn whether the read model
lives in memory or Postgres. It mirrors the semantics `InMemoryMissionListReadModel` pins — tenant-
scoped fail-closed reads, newest-first ordering, exact status/type filters, case-insensitive title
search, bounded 1-based paging — but enforces them **in SQL** (the `WHERE tenant_id = %(tenant)s`
predicate is the isolation guard; no query can widen it).

The psycopg driver is imported **lazily**, inside the methods that touch the database, so the module
(and the pure in-memory adapter) import with no driver present — matching `PostgresMissionStore`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pipeline_contracts import TenantContext

from mission_read_model.models import MissionListItem, MissionPage
from mission_read_model.ports import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from mission_read_model.schema import DEFAULT_TABLE

if TYPE_CHECKING:  # import only for type checkers; never required to import this module
    import psycopg

_MISSING_PG = (
    "PostgresMissionListReadModel needs the 'psycopg' package. "
    "Install the optional extra: mission-read-model[postgres]"
)

_COLUMNS = (
    "mission_id",
    "tenant_id",
    "mission_type",
    "title",
    "status",
    "created_at",
    "updated_at",
)


def _load_pg() -> tuple[Any, Any]:
    """Import psycopg lazily: the module and the dict row factory. Kept out of module import so the
    package loads without the driver."""
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - exercised only without the driver installed
        raise ImportError(_MISSING_PG) from exc
    return psycopg, dict_row


def _item_from_row(row: dict[str, Any]) -> MissionListItem:
    return MissionListItem(
        mission_id=row["mission_id"],
        tenant_id=row["tenant_id"],
        mission_type=row["mission_type"],
        title=row["title"],
        status=row["status"],
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


class PostgresMissionListReadModel:
    def __init__(
        self,
        *,
        dsn: str | None = None,
        connection: psycopg.Connection | None = None,
        table: str = DEFAULT_TABLE,
    ) -> None:
        self._table = table
        self._owns_conn = connection is None
        if connection is not None:
            self._conn = connection
        else:
            psycopg, _ = _load_pg()
            # autocommit: a record/read is a single statement and must be durable on return.
            self._conn = psycopg.connect(dsn, autocommit=True)

    def record(self, item: MissionListItem) -> None:
        """Upsert the projection by `mission_id` (idempotent). A re-projection on a later
        transition overwrites the row with the mission's newest snapshot, bumping the ops stamp."""
        placeholders = ", ".join(f"%({col})s" for col in _COLUMNS)
        assignments = ", ".join(
            f"{col} = EXCLUDED.{col}" for col in _COLUMNS if col != "mission_id"
        )
        sql = (
            f"INSERT INTO {self._table} ({', '.join(_COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT (mission_id) DO UPDATE SET {assignments}, row_updated_at = now()"
        )
        params = {
            "mission_id": item.mission_id,
            "tenant_id": item.tenant_id,
            "mission_type": item.mission_type,
            "title": item.title,
            "status": item.status,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        self._conn.execute(sql, params)

    def get(self, mission_id: str, tenant: TenantContext) -> MissionListItem | None:
        """One mission's projection, tenant-scoped in SQL — a foreign-tenant row is not found."""
        _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(_COLUMNS)} FROM {self._table} "
            f"WHERE mission_id = %(id)s AND tenant_id = %(tenant_id)s"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"id": mission_id, "tenant_id": tenant.tenant_id})
            row = cur.fetchone()
        return _item_from_row(row) if row is not None else None

    def list_missions(
        self,
        tenant: TenantContext,
        *,
        status: str | None = None,
        mission_type: str | None = None,
        query: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> MissionPage:
        page = max(page, 1)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        _, dict_row = _load_pg()

        # Tenant predicate first and always — the fail-closed isolation guard (ADR 0040 §5). The
        # optional filters are bound params; the title search is a case-insensitive LIKE.
        where = ["tenant_id = %(tenant_id)s"]
        params: dict[str, Any] = {"tenant_id": tenant.tenant_id}
        if status:
            where.append("status = %(status)s")
            params["status"] = status
        if mission_type:
            where.append("mission_type = %(mission_type)s")
            params["mission_type"] = mission_type
        if query and query.strip():
            where.append("title ILIKE %(needle)s")
            params["needle"] = f"%{query.strip()}%"
        where_sql = " AND ".join(where)

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT count(*) AS n FROM {self._table} WHERE {where_sql}", params)
            total_row = cur.fetchone()
            total = int(total_row["n"]) if total_row else 0

            page_params = dict(params)
            page_params["limit"] = page_size
            page_params["offset"] = (page - 1) * page_size
            cur.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM {self._table} WHERE {where_sql} "
                f"ORDER BY updated_at DESC, created_at DESC, mission_id DESC "
                f"LIMIT %(limit)s OFFSET %(offset)s",
                page_params,
            )
            rows = cur.fetchall()

        items = tuple(_item_from_row(row) for row in rows)
        return MissionPage(items=items, page=page, page_size=page_size, total=total)

    def close(self) -> None:
        """Close the connection only if this adapter opened it."""
        if self._owns_conn:
            self._conn.close()
