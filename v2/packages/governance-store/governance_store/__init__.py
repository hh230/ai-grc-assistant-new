"""Rasheed V2 **Governance Store** (ADR 0066) — durable persistence for the AI Governance
Planning Engine.

This slice ships the schema and migrations for five tenant-scoped tables — `organization_profiles`,
`discovery_sessions`, `discovery_answers`, `governance_plans`, `governance_plan_items` — following
the same discipline as `mission_store/schema.py` (ADR 0043 §7): `schema.py` is the single source of
truth for DDL, mirrored by idempotent hand-written migrations in `migrations/`, kept in lock-step
by a parity test.

`codec.py`/`store.py` round-trip `DiscoverySession` (+ its append-only answer log) for the
Governance Discovery engine (Phase 2). `governance_plans`/`governance_plan_items` and
`organization_profiles` remain schema-only until the Governance Planning Mission (Phase 3) and
profile-tracking work land — this package adds repositories incrementally as each aggregate is
ready, without changing the schema underneath them.
"""

from governance_store.codec import applicability_from_dict, applicability_to_dict
from governance_store.config import (
    DEFAULT_DSN,
    TABLE_DISCOVERY_ANSWERS,
    TABLE_DISCOVERY_SESSIONS,
    TABLE_GOVERNANCE_PLAN_EVENTS,
    TABLE_GOVERNANCE_PLAN_ITEMS,
    TABLE_GOVERNANCE_PLANS,
    TABLE_ORGANIZATION_PROFILES,
    dsn,
)
from governance_store.knowledge_store import PostgresKnowledgeStore
from governance_store.schema import apply_schema, create_table_sql, index_sql
from governance_store.store import AnswerRecord, PostgresGovernanceStore

__all__ = [
    "PostgresKnowledgeStore",
    "apply_schema",
    "create_table_sql",
    "index_sql",
    "dsn",
    "DEFAULT_DSN",
    "TABLE_ORGANIZATION_PROFILES",
    "TABLE_DISCOVERY_SESSIONS",
    "TABLE_DISCOVERY_ANSWERS",
    "TABLE_GOVERNANCE_PLANS",
    "TABLE_GOVERNANCE_PLAN_ITEMS",
    "TABLE_GOVERNANCE_PLAN_EVENTS",
    "PostgresGovernanceStore",
    "AnswerRecord",
    "applicability_to_dict",
    "applicability_from_dict",
]
