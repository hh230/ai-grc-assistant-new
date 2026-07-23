"""Mission Read Model — the first product-side read model (Domain-Model §3; Execution Slice S1).

The Missions View asks one question: *"which missions does this tenant have?"* The frozen Core can
answer *get one mission* but not *list a tenant's missions* — and it never persists the product's
Mission Type or scope (it stores a free-text `goal`). This package fills that gap as a **CQRS read
model**: a tenant-scoped, fail-closed projection carrying the product metadata (type, title) plus a
status snapshot, with filter/search/paging. It writes no missions; the Core owns all writes.

Public surface:
- `MissionListItem` / `MissionPage` — the read-side data the list renders.
- `MissionListReadModel` — the port the API reads through.
- `InMemoryMissionListReadModel` — the driver-free adapter (tests / local).
- `PostgresMissionListReadModel` — the durable adapter (deployment), same port; import triggers a
  lazy psycopg load only when instantiated.
- `create_table_sql` — the read-model table DDL (ADR 0053).
"""

from __future__ import annotations

from mission_read_model.memory import InMemoryMissionListReadModel
from mission_read_model.models import MissionListItem, MissionPage
from mission_read_model.ports import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MissionListReadModel,
)
from mission_read_model.postgres import PostgresMissionListReadModel
from mission_read_model.schema import DEFAULT_TABLE, create_table_sql

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_TABLE",
    "MAX_PAGE_SIZE",
    "InMemoryMissionListReadModel",
    "MissionListItem",
    "MissionListReadModel",
    "MissionPage",
    "PostgresMissionListReadModel",
    "create_table_sql",
]
