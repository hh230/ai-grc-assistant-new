"""Connection configuration for the Postgres Mission Store (ADR 0042 §9, §12.3, step 4).

The DSN comes from the environment (`MISSION_STORE_DSN`), defaulting to the isolated V2
database `rasheed_v2` — the same isolated dev database the Retrieval Engine's pgvector
adapter uses, never V1's `aigrc`. No credentials are hardcoded beyond the local dev default.
"""

from __future__ import annotations

import os

# Isolated V2 database on the local dev server. Override in any real deployment. Missions and
# knowledge vectors coexist in `rasheed_v2` — the V2 product/platform database — but in their
# own tables; nothing here touches V1's `aigrc`.
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_v2"

TABLE = "missions"


def dsn() -> str:
    return os.environ.get("MISSION_STORE_DSN", DEFAULT_DSN)
