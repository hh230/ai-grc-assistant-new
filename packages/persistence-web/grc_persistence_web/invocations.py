"""The concrete `ai_tool_invocations` writer — CLAUDE.md §19's audit trail, made durable.

Implements `grc_tools.ToolInvocationRecorder` so the Tool Registry never depends on this
package directly; the composition root binds this concrete recorder in production.
"""

from __future__ import annotations

import json

from grc_tools import ToolInvocationRecord, ToolInvocationRecorder

from .pool import Database

_INSERT_SQL = """
INSERT INTO ai_tool_invocations (
  id, tenant_id, tool_name, tool_version, agent, caller, model, prompt_version,
  inputs_hash, output_ref, confidence, citations, requires_human_approval, status,
  error_detail, prompt_tokens, completion_tokens, total_tokens, latency_ms, cost_usd,
  created_at
) VALUES (
  $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13, $14, $15, $16, $17, $18,
  $19, $20, $21
)
"""


class PostgresToolInvocationRecorder(ToolInvocationRecorder):
    """Writes every Tool invocation to `ai_tool_invocations`. Never raises into the caller's
    path — a recording failure is logged, not propagated, so an audit-log outage cannot take
    down the AI runtime it is meant to be watching."""

    def __init__(self, database: Database, *, logger: object | None = None) -> None:
        self._database = database
        self._logger = logger

    async def record(self, entry: ToolInvocationRecord) -> None:
        try:
            async with self._database.pool.acquire() as connection:
                await connection.execute(
                    _INSERT_SQL,
                    entry.id,
                    entry.tenant_id,
                    entry.tool_name,
                    entry.tool_version,
                    entry.agent,
                    entry.caller,
                    entry.model,
                    entry.prompt_version,
                    entry.inputs_hash,
                    entry.output_ref,
                    entry.confidence,
                    json.dumps(list(entry.citations)),
                    entry.requires_human_approval,
                    entry.status.value,
                    entry.error_detail,
                    entry.prompt_tokens,
                    entry.completion_tokens,
                    entry.total_tokens,
                    entry.latency_ms,
                    entry.cost_usd,
                    entry.created_at,
                )
        except Exception:  # noqa: BLE001 - audit logging must never break the caller's path
            if self._logger is not None:
                log = getattr(self._logger, "error", None)
                if callable(log):
                    log(
                        "ai_tool_invocation_record_failed",
                        extra={"tool_name": entry.tool_name, "invocation_id": entry.id},
                    )
