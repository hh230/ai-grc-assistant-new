"""realign knowledge_sources with the KnowledgeSource domain refactor

KnowledgeSource moved from a flat organization_id + content/ingestion fields to the
two-library scope model (CLAUDE.md's Framework Engine): scope_kind ("global" or
"organization") plus scope_organization_id, short_code, authority, jurisdiction,
knowledge_domain, document_type, framework_refs, tags, canonical_languages, steward and
current_version_id. Content, locator and ingestion status now live on the separate
KnowledgeSourceVersion aggregate, which has no persistence yet.

Uses batch mode throughout: SQLite (the hermetic test engine) cannot ALTER constraints or
column types directly, only via batch mode's copy-and-move strategy; on PostgreSQL, batch
mode transparently falls back to plain ALTER statements.

Revision ID: 0002_knowledge_source_scope
Revises: 0001_initial_schema
Create Date: 2026-07-09 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from grc_persistence.db.types import JSONColumn

# revision identifiers, used by Alembic.
revision: str = "0002_knowledge_source_scope"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_sources") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_knowledge_sources_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_index(op.f("ix_knowledge_sources_organization_id"))
        batch_op.drop_column("organization_id")
        batch_op.drop_column("source_type")
        batch_op.drop_column("locator_uri")
        batch_op.drop_column("language")
        batch_op.drop_column("ingestion_status")
        batch_op.drop_column("checksum_algorithm")
        batch_op.drop_column("checksum_value")
        batch_op.drop_column("failure_reason")

        batch_op.add_column(sa.Column("scope_kind", sa.String(length=16), nullable=False))
        batch_op.add_column(
            sa.Column("scope_organization_id", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(sa.Column("short_code", sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column("authority", sa.String(length=255), nullable=False))
        batch_op.add_column(sa.Column("jurisdiction", sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column("knowledge_domain", sa.String(length=32), nullable=False))
        batch_op.add_column(sa.Column("document_type", sa.String(length=32), nullable=False))
        batch_op.add_column(sa.Column("framework_refs", JSONColumn, nullable=False))
        batch_op.add_column(sa.Column("tags", JSONColumn, nullable=False))
        batch_op.add_column(sa.Column("canonical_languages", JSONColumn, nullable=False))
        batch_op.add_column(sa.Column("steward", JSONColumn, nullable=True))
        batch_op.add_column(sa.Column("current_version_id", sa.String(length=255), nullable=True))
        # `title` keeps its column name but changes shape (str -> JSON-encoded LocalizedText).
        batch_op.alter_column(
            "title",
            existing_type=sa.String(length=255),
            type_=JSONColumn,
            postgresql_using="to_jsonb(title)",
        )

        batch_op.create_foreign_key(
            op.f("fk_knowledge_sources_scope_organization_id_organizations"),
            "organizations",
            ["scope_organization_id"],
            ["id"],
        )
        batch_op.create_index(
            op.f("ix_knowledge_sources_scope_organization_id"), ["scope_organization_id"]
        )
        batch_op.create_index(op.f("ix_knowledge_sources_short_code"), ["short_code"])


def downgrade() -> None:
    with op.batch_alter_table("knowledge_sources") as batch_op:
        batch_op.drop_index(op.f("ix_knowledge_sources_short_code"))
        batch_op.drop_index(op.f("ix_knowledge_sources_scope_organization_id"))
        batch_op.drop_constraint(
            op.f("fk_knowledge_sources_scope_organization_id_organizations"), type_="foreignkey"
        )

        batch_op.alter_column(
            "title",
            existing_type=JSONColumn,
            type_=sa.String(length=255),
            postgresql_using="title->0->>'text'",
        )

        batch_op.drop_column("current_version_id")
        batch_op.drop_column("steward")
        batch_op.drop_column("canonical_languages")
        batch_op.drop_column("tags")
        batch_op.drop_column("framework_refs")
        batch_op.drop_column("document_type")
        batch_op.drop_column("knowledge_domain")
        batch_op.drop_column("jurisdiction")
        batch_op.drop_column("authority")
        batch_op.drop_column("short_code")
        batch_op.drop_column("scope_organization_id")
        batch_op.drop_column("scope_kind")

        batch_op.add_column(sa.Column("failure_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("checksum_value", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("checksum_algorithm", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("ingestion_status", sa.String(length=32), nullable=False))
        batch_op.add_column(sa.Column("language", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("locator_uri", sa.Text(), nullable=False))
        batch_op.add_column(sa.Column("source_type", sa.String(length=32), nullable=False))
        batch_op.add_column(sa.Column("organization_id", sa.String(length=255), nullable=False))
        batch_op.create_index(
            op.f("ix_knowledge_sources_organization_id"), ["organization_id"]
        )
        batch_op.create_foreign_key(
            op.f("fk_knowledge_sources_organization_id_organizations"),
            "organizations",
            ["organization_id"],
            ["id"],
        )
