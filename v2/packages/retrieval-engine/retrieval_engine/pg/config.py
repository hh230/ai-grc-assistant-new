"""Connection configuration for the pgvector adapter. The DSN comes from the environment
(`RETRIEVAL_PG_DSN`), defaulting to the isolated V2 database `rasheed_v2` — never V1's
`aigrc`. No credentials are hardcoded beyond the local dev default."""

from __future__ import annotations

import os

# Isolated V2 database on the local dev pgvector server. Override in any real deployment.
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_v2"

TABLE = "knowledge_vectors"
EMBEDDING_DIMENSION = 1536
DEFAULT_EF_SEARCH = 100


def dsn() -> str:
    return os.environ.get("RETRIEVAL_PG_DSN", DEFAULT_DSN)
