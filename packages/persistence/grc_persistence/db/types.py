"""Portable column types.

The production target is PostgreSQL (ADR 0012), where structured value-object collections
are stored as ``JSONB``. The same models must also run on SQLite (used by the hermetic
integration tests), so we expose a single :data:`JSONColumn` type that renders as ``JSONB``
on PostgreSQL and the generic ``JSON`` type elsewhere.
"""

from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeEngine

#: ``JSONB`` on PostgreSQL, generic ``JSON`` (TEXT-backed) on every other dialect.
JSONColumn: TypeEngine[object] = JSON().with_variant(JSONB(), "postgresql")
