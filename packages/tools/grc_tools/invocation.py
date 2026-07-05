"""The audit record every Tool invocation produces, and the port that persists it.

CLAUDE.md §19 requires every AI action to record what was asked, what was retrieved, which
model/prompt, which tools ran, confidence, citations, cost, and any human-gate outcome. A
``ToolInvocationRecord`` is that record for one Tool call; ``ToolInvocationRecorder`` is the
outbound port so the Tool Registry never depends on a concrete store — the composition root
binds it to ``packages/persistence-web`` in production and to an in-memory fake in tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class InvocationStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


@dataclass(frozen=True)
class ToolInvocationRecord:
    """An append-only audit record for one Tool invocation (CLAUDE.md §19)."""

    id: str
    tenant_id: str | None
    tool_name: str
    tool_version: str
    caller: str
    status: InvocationStatus
    requires_human_approval: bool
    agent: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    inputs_hash: str | None = None
    output_ref: str | None = None
    confidence: float | None = None
    citations: tuple[str, ...] = ()
    error_detail: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    cost_usd: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ToolInvocationRecorder(ABC):
    """Outbound port: persist a Tool invocation record. Never raises into the caller's path."""

    @abstractmethod
    async def record(self, entry: ToolInvocationRecord) -> None: ...


class NullToolInvocationRecorder(ToolInvocationRecorder):
    """Discards records. Used only where an explicit recorder would be noise (e.g. unit tests)."""

    async def record(self, entry: ToolInvocationRecord) -> None:
        return None
