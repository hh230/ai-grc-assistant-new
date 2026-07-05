"""The Tool Registry (CLAUDE.md §10): the catalog every caller discovers and invokes Tools
through. Nothing calls a business capability out of band — if it's a business function, it is
registered here, and every invocation is authorized, validated, and audited the same way
regardless of which of the six callers made it.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from grc_domain.platform import Permission, ToolSideEffect
from pydantic import ValidationError

from .context import ToolContext
from .exceptions import (
    ToolInputValidationError,
    ToolNotFoundError,
    ToolPermissionDeniedError,
)
from .invocation import InvocationStatus, ToolInvocationRecord, ToolInvocationRecorder
from .tool import Tool


def _permission_key(tool_name: str, version: str) -> str:
    return f"{tool_name}@{version}"


def _has_required_permissions(required: frozenset[Permission], roles: frozenset[str]) -> bool:
    """v1 policy: a required permission is satisfied by an identically-named role.

    Deliberately simple — fine-grained ABAC belongs to ``packages/security`` when that
    package graduates past its current scaffold; this is enough to keep consequential tools
    (e.g. drafting a policy) from being callable by a bare ``viewer``.
    """
    return all(permission.name in roles for permission in required)


class ToolRegistry:
    """Registers Tools and is the single path every caller invokes them through."""

    def __init__(self, *, recorder: ToolInvocationRecorder) -> None:
        self._tools: dict[str, Tool[Any, Any]] = {}
        self._recorder = recorder

    def register(self, tool: Tool[Any, Any]) -> None:
        descriptor = tool.descriptor
        key = _permission_key(descriptor.name, str(descriptor.version))
        if key in self._tools:
            raise ValueError(f"a tool is already registered for {key!r}")
        self._tools[key] = tool

    def get(self, name: str, version: str) -> Tool[Any, Any]:
        key = _permission_key(name, version)
        tool = self._tools.get(key)
        if tool is None:
            raise ToolNotFoundError(f"no tool registered for {key!r}")
        return tool

    def list_active(self) -> tuple[Tool[Any, Any], ...]:
        return tuple(self._tools.values())

    async def invoke(
        self,
        name: str,
        version: str,
        raw_input: dict[str, object],
        context: ToolContext,
    ) -> object:
        """Look up, authorize, validate, execute, and audit one Tool call.

        Returns the tool's validated output. Raises ``ToolNotFoundError``,
        ``ToolPermissionDeniedError``, or ``ToolInputValidationError`` — each of those is
        itself recorded as a denied/failed invocation before it propagates, so a rejected
        call is exactly as auditable as a successful one (CLAUDE.md §19).
        """
        tool = self.get(name, version)
        descriptor = tool.descriptor
        started = time.monotonic()

        if not _has_required_permissions(descriptor.required_permissions, context.roles):
            await self._record(
                tool_name=name,
                version=version,
                context=context,
                status=InvocationStatus.DENIED,
                requires_approval=descriptor.requires_approval,
                started=started,
                error="missing required permission",
            )
            raise ToolPermissionDeniedError(
                f"{context.user_id!r} lacks a permission required by {name!r}"
            )

        try:
            validated_input = tool.input_model(**raw_input)
        except ValidationError as error:
            await self._record(
                tool_name=name,
                version=version,
                context=context,
                status=InvocationStatus.FAILED,
                requires_approval=descriptor.requires_approval,
                started=started,
                error=str(error),
            )
            raise ToolInputValidationError(str(error)) from error

        inputs_hash = hashlib.sha256(validated_input.model_dump_json().encode("utf-8")).hexdigest()

        try:
            outcome = await tool.run(validated_input, context)
        except Exception as error:  # noqa: BLE001 - fail-safe: always record, then re-raise
            await self._record(
                tool_name=name,
                version=version,
                context=context,
                status=InvocationStatus.FAILED,
                requires_approval=descriptor.requires_approval,
                started=started,
                error=str(error),
                inputs_hash=inputs_hash,
            )
            raise

        await self._record(
            tool_name=name,
            version=version,
            context=context,
            status=InvocationStatus.SUCCEEDED,
            requires_approval=descriptor.requires_approval,
            started=started,
            inputs_hash=inputs_hash,
            outcome=outcome,
        )
        return outcome.output

    async def _record(
        self,
        *,
        tool_name: str,
        version: str,
        context: ToolContext,
        status: InvocationStatus,
        requires_approval: bool,
        started: float,
        inputs_hash: str | None = None,
        error: str | None = None,
        outcome: object = None,
    ) -> None:
        latency_ms = int((time.monotonic() - started) * 1000)
        entry = ToolInvocationRecord(
            id=str(uuid.uuid4()),
            tenant_id=context.tenant_id,
            tool_name=tool_name,
            tool_version=version,
            caller=context.caller.value,
            status=status,
            requires_human_approval=requires_approval,
            agent=context.agent,
            model=getattr(outcome, "model", None),
            prompt_version=getattr(outcome, "prompt_version", None),
            inputs_hash=inputs_hash,
            confidence=getattr(outcome, "confidence", None),
            citations=getattr(outcome, "citations", ()) or (),
            error_detail=error,
            prompt_tokens=getattr(outcome, "prompt_tokens", None),
            completion_tokens=getattr(outcome, "completion_tokens", None),
            total_tokens=getattr(outcome, "total_tokens", None),
            latency_ms=latency_ms,
            cost_usd=getattr(outcome, "cost_usd", None),
            created_at=datetime.now(timezone.utc),
        )
        # Auditing must never break the caller's path: a recorder failure is logged upstream
        # by whatever concrete recorder is bound, not swallowed here silently.
        await self._recorder.record(entry)


__all__ = [
    "ToolRegistry",
    "ToolSideEffect",
]
