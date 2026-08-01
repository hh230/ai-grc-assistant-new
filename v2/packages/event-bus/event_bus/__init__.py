"""Rasheed V2 Event Bus & Audit Trail (Phase 13).

A provider-agnostic, synchronous, in-process domain-event architecture: immutable domain
events, an `EventBus` port, and a local `InProcessEventBus` dispatcher — no Kafka, no
RabbitMQ, no Redis. Plus the Audit Trail domain model (`AuditRecord`) and its `AuditSink`
interface (model + interfaces only, no persistence). Depends on nothing.
"""

from event_bus.audit import (
    VALIDATION_NOT_CONFIGURED,
    AuditRecord,
    AuditSink,
    AuditTrailBuilder,
    InMemoryAuditSink,
)
from event_bus.bus import (
    ALL_EVENTS,
    ErrorHandler,
    EventBus,
    EventHandler,
    InProcessEventBus,
    RecordingEventBus,
)
from event_bus.events import (
    AnswerValidated,
    DomainEvent,
    GenerationCompleted,
    PipelineCompleted,
    PromptBuilt,
    RetrievalCompleted,
    now,
)

__all__ = [
    # events
    "DomainEvent",
    "RetrievalCompleted",
    "PromptBuilt",
    "GenerationCompleted",
    "AnswerValidated",
    "PipelineCompleted",
    "now",
    # bus
    "EventBus",
    "InProcessEventBus",
    "RecordingEventBus",
    "EventHandler",
    "ErrorHandler",
    "ALL_EVENTS",
    # audit
    "AuditRecord",
    "AuditSink",
    "InMemoryAuditSink",
    "AuditTrailBuilder",
    "VALIDATION_NOT_CONFIGURED",
]
