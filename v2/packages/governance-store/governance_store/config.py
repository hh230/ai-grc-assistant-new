"""Connection configuration for the Postgres Governance Store (ADR 0066).

The DSN comes from the environment (`GOVERNANCE_STORE_DSN`), defaulting to the same isolated V2
database `rasheed_v2` that `mission-store` uses — governance tables coexist there in their own
tables, nothing here touches V1's `aigrc`.
"""

from __future__ import annotations

import os

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_v2"

TABLE_ORGANIZATION_PROFILES = "organization_profiles"
TABLE_DISCOVERY_SESSIONS = "discovery_sessions"
TABLE_DISCOVERY_ANSWERS = "discovery_answers"
TABLE_GOVERNANCE_PLANS = "governance_plans"
TABLE_GOVERNANCE_PLAN_ITEMS = "governance_plan_items"
TABLE_GOVERNANCE_PLAN_EVENTS = "governance_plan_events"


def dsn() -> str:
    return os.environ.get("GOVERNANCE_STORE_DSN", DEFAULT_DSN)
