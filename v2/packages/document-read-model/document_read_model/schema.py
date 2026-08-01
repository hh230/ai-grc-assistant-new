"""Schema DDL for the Document read-model table (ADR 0053), parameterised by table name.

The read model is a self-contained projection: one row per document carrying the Knowledge-view
fields (`evidence_kind`, the `status` snapshot, `filename`, `uploaded_at`, `size`). The projector
upserts rows here after ingestion; `GET /v1/documents` reads them. The adapter never issues DDL at
runtime — this is the single source of truth for the table shape, used by a throwaway test table and
(later) a canonical migration.

Indexes support the Knowledge view's access pattern: filter by tenant (always), newest-first; and
group by `evidence_kind` within a tenant (the Evidence Collections overview).
"""

from __future__ import annotations

DEFAULT_TABLE = "document_read_model"


def create_table_sql(table: str = DEFAULT_TABLE) -> str:
    return f"""\
CREATE TABLE IF NOT EXISTS {table} (
    document_id  text             PRIMARY KEY,
    tenant_id    text             NOT NULL,
    filename     text             NOT NULL,
    evidence_kind text            NOT NULL,
    status       text             NOT NULL,
    uploaded_at  double precision NOT NULL,
    size         bigint           NOT NULL DEFAULT 0,
    row_updated_at timestamptz    NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS {table}_tenant_uploaded_idx
    ON {table} (tenant_id, uploaded_at DESC, document_id DESC);
CREATE INDEX IF NOT EXISTS {table}_tenant_kind_idx ON {table} (tenant_id, evidence_kind);
"""
