"""Rasheed V2 **Mission Store** (ADR 0043, Slice 1) — the durable `MissionStorePort`.

The Mission Engine reaches all persistence through the `MissionStorePort` (ADR 0042 §12.3).
Phase 15 shipped that port with a reference `InMemoryMissionStore`; this package is the
production implementation behind the *same* port: a PostgreSQL-backed store that round-trips the
`Mission` aggregate — its versioned plan, full plan-version history, step results, lifecycle
state, and tenant scope. Because it implements the frozen port unchanged, it is a drop-in for the
in-memory store: the Mission Engine and aggregate are untouched.

    from mission_engine import EchoExecutor, MissionEngine
    from mission_store import PostgresMissionStore
    from pipeline_contracts import TenantContext

    store = PostgresMissionStore(dsn="postgresql://.../rasheed_v2")
    engine = MissionEngine(store=store, executor=EchoExecutor())
    tenant = TenantContext(tenant_id="org_acme", principal_id="u_owner", roles=("owner",))
    mission = engine.run_simple("MFA lookup", tenant, "what does NCA ECC say about MFA?")

The `codec` module (pure) owns the aggregate↔row translation and imports no driver; `store`
imports psycopg lazily, so this package imports with or without the database driver present.
"""

from mission_store.codec import CURRENT_PAYLOAD_VERSION, mission_from_row, mission_to_row
from mission_store.config import DEFAULT_DSN, TABLE, dsn
from mission_store.errors import (
    IdempotencyConflict,
    MissionStoreError,
    SerializationError,
    UnsupportedPayloadSchemaVersion,
)
from mission_store.outbox import OutboxRelay, OutboxSink
from mission_store.outbox_codec import (
    CURRENT_OUTBOX_PAYLOAD_VERSION,
    EVENT_REGISTRY,
    OutboxRecord,
    event_from_record,
    event_to_row,
)
from mission_store.outbox_errors import OutboxError, UnsupportedEventType
from mission_store.outbox_publisher import DeliveryBusPublisher, OutboxPublisher
from mission_store.outbox_schema import OUTBOX_TABLE, apply_outbox_schema
from mission_store.store import PostgresMissionStore
from mission_store.unit_of_work import UnitOfWork, UnitOfWorkError

__all__ = [
    "PostgresMissionStore",
    # unit of work (Slice 3): the transaction boundary; owns the connection, owns no stores
    "UnitOfWork",
    "UnitOfWorkError",
    # transactional outbox (Slice 4): capture sink + drain relay + publisher port
    "OutboxSink",
    "OutboxRelay",
    "OutboxPublisher",
    "DeliveryBusPublisher",
    "OutboxRecord",
    "event_to_row",
    "event_from_record",
    "EVENT_REGISTRY",
    "CURRENT_OUTBOX_PAYLOAD_VERSION",
    "OUTBOX_TABLE",
    "apply_outbox_schema",
    # error taxonomy: MissionStoreError ├─ SerializationError └─ UnsupportedPayloadSchemaVersion
    #                                    ├─ IdempotencyConflict
    #                                    ├─ UnitOfWorkError
    #                                    └─ OutboxError └─ UnsupportedEventType
    "MissionStoreError",
    "SerializationError",
    "UnsupportedPayloadSchemaVersion",
    "IdempotencyConflict",
    "OutboxError",
    "UnsupportedEventType",
    # serialization (pure, driver-free)
    "mission_to_row",
    "mission_from_row",
    "CURRENT_PAYLOAD_VERSION",
    # configuration
    "dsn",
    "DEFAULT_DSN",
    "TABLE",
]
