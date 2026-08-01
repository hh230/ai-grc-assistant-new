"""`PostgresDocumentReadModel` — the durable adapter (ADR 0053), same port as the in-memory one.

A drop-in `DocumentReadModel`: the API host and the projector never learn whether the read model
lives in memory or Postgres. It mirrors the semantics `InMemoryDocumentReadModel` pins — tenant-
scoped fail-closed reads, newest-first ordering, an exact `evidence_kind` filter, collection
grouping in the product's display order, idempotent upsert by `document_id` — but enforces them
**in SQL** (the `WHERE tenant_id = %(tenant)s` predicate is the isolation guard; nothing widens it).

The psycopg driver is imported **lazily**, inside the methods that touch the database, so the module
(and the pure in-memory adapter) import with no driver present — matching the Mission read model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pipeline_contracts import TenantContext

from document_read_model.kinds import kind_sort_key
from document_read_model.models import DocumentItem, EvidenceCollection
from document_read_model.schema import DEFAULT_TABLE

if TYPE_CHECKING:  # import only for type checkers; never required to import this module
    import psycopg

_MISSING_PG = (
    "PostgresDocumentReadModel needs the 'psycopg' package. "
    "Install the optional extra: document-read-model[postgres]"
)

_COLUMNS = (
    "document_id",
    "tenant_id",
    "filename",
    "evidence_kind",
    "status",
    "uploaded_at",
    "size",
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


def _item_from_row(row: dict[str, Any]) -> DocumentItem:
    return DocumentItem(
        document_id=row["document_id"],
        tenant_id=row["tenant_id"],
        filename=row["filename"],
        evidence_kind=row["evidence_kind"],
        status=row["status"],
        uploaded_at=float(row["uploaded_at"]),
        size=int(row["size"]),
    )


class PostgresDocumentReadModel:
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

    def record(self, item: DocumentItem) -> None:
        """Upsert the projection by `document_id` (idempotent). A re-projection on a status change
        (`ingesting → ready`) overwrites the row with the document's newest snapshot."""
        placeholders = ", ".join(f"%({col})s" for col in _COLUMNS)
        assignments = ", ".join(
            f"{col} = EXCLUDED.{col}" for col in _COLUMNS if col != "document_id"
        )
        sql = (
            f"INSERT INTO {self._table} ({', '.join(_COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT (document_id) DO UPDATE SET {assignments}, row_updated_at = now()"
        )
        params = {
            "document_id": item.document_id,
            "tenant_id": item.tenant_id,
            "filename": item.filename,
            "evidence_kind": item.evidence_kind,
            "status": item.status,
            "uploaded_at": item.uploaded_at,
            "size": item.size,
        }
        self._conn.execute(sql, params)

    def get(self, document_id: str, tenant: TenantContext) -> DocumentItem | None:
        """One document's projection, tenant-scoped in SQL — a foreign-tenant row is not found."""
        _, dict_row = _load_pg()
        sql = (
            f"SELECT {', '.join(_COLUMNS)} FROM {self._table} "
            f"WHERE document_id = %(id)s AND tenant_id = %(tenant_id)s"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, {"id": document_id, "tenant_id": tenant.tenant_id})
            row = cur.fetchone()
        return _item_from_row(row) if row is not None else None

    def list_documents(
        self,
        tenant: TenantContext,
        *,
        evidence_kind: str | None = None,
    ) -> tuple[DocumentItem, ...]:
        _, dict_row = _load_pg()
        # Tenant predicate first and always — the fail-closed isolation guard (ADR 0040 §5).
        where = ["tenant_id = %(tenant_id)s"]
        params: dict[str, Any] = {"tenant_id": tenant.tenant_id}
        if evidence_kind:
            where.append("evidence_kind = %(evidence_kind)s")
            params["evidence_kind"] = evidence_kind
        where_sql = " AND ".join(where)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM {self._table} WHERE {where_sql} "
                f"ORDER BY uploaded_at DESC, document_id DESC",
                params,
            )
            rows = cur.fetchall()
        return tuple(_item_from_row(row) for row in rows)

    def list_collections(self, tenant: TenantContext) -> tuple[EvidenceCollection, ...]:
        _, dict_row = _load_pg()
        # Group within the tenant; order in Python so the display order matches KIND_ORDER exactly
        # (unknown kinds last) — identical to the in-memory adapter.
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT evidence_kind, count(*) AS n FROM {self._table} "
                f"WHERE tenant_id = %(tenant_id)s GROUP BY evidence_kind",
                {"tenant_id": tenant.tenant_id},
            )
            rows = cur.fetchall()
        rows.sort(key=lambda row: kind_sort_key(row["evidence_kind"]))
        return tuple(
            EvidenceCollection(evidence_kind=row["evidence_kind"], count=int(row["n"]))
            for row in rows
        )

    def close(self) -> None:
        """Close the connection only if this adapter opened it."""
        if self._owns_conn:
            self._conn.close()
