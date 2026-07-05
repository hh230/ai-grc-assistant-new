"""Unit tests for the Tool Registry: registration, authorization, validation, and audit."""

from __future__ import annotations

import pytest
from grc_domain.platform import Permission, ToolDescriptor, ToolSideEffect
from grc_domain.shared.identifiers import ToolId
from grc_domain.shared.value_objects import SemanticVersion
from grc_tools import (
    Tool,
    ToolCaller,
    ToolContext,
    ToolInputValidationError,
    ToolInvocationRecord,
    ToolInvocationRecorder,
    ToolNotFoundError,
    ToolOutcome,
    ToolPermissionDeniedError,
    ToolRegistry,
)
from pydantic import BaseModel


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    text: str


class RecordingRecorder(ToolInvocationRecorder):
    def __init__(self) -> None:
        self.entries: list[ToolInvocationRecord] = []

    async def record(self, entry: ToolInvocationRecord) -> None:
        self.entries.append(entry)


class EchoTool(Tool[EchoInput, EchoOutput]):
    def __init__(self, *, required_permissions: frozenset[Permission] = frozenset()) -> None:
        self._descriptor = ToolDescriptor.register(
            id=ToolId("echo-tool"),
            name="echo_tool",
            version=SemanticVersion(1, 0, 0),
            description="Echoes its input back.",
            side_effect=ToolSideEffect.READ_ONLY,
            required_permissions=required_permissions,
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    @property
    def input_model(self) -> type[EchoInput]:
        return EchoInput

    @property
    def output_model(self) -> type[EchoOutput]:
        return EchoOutput

    async def run(self, input: EchoInput, context: ToolContext) -> ToolOutcome[EchoOutput]:
        return ToolOutcome(output=EchoOutput(text=input.text), confidence=1.0, citations=("src:1",))


def context(**overrides: object) -> ToolContext:
    defaults: dict[str, object] = {
        "caller": ToolCaller.TEST,
        "tenant_id": "dev-org",
        "user_id": "dev-user",
        "roles": frozenset({"owner"}),
    }
    defaults.update(overrides)
    return ToolContext(**defaults)  # type: ignore[arg-type]


async def test_invoke_returns_validated_output_and_records_success() -> None:
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(EchoTool())

    output = await registry.invoke("echo_tool", "1.0.0", {"text": "hello"}, context())

    assert output == EchoOutput(text="hello")
    assert len(recorder.entries) == 1
    entry = recorder.entries[0]
    assert entry.status.value == "succeeded"
    assert entry.tool_name == "echo_tool"
    assert entry.confidence == 1.0
    assert entry.citations == ("src:1",)
    assert entry.inputs_hash is not None


async def test_invoke_raises_for_unknown_tool() -> None:
    registry = ToolRegistry(recorder=RecordingRecorder())
    with pytest.raises(ToolNotFoundError):
        await registry.invoke("nonexistent", "1.0.0", {}, context())


async def test_invoke_denies_and_records_when_permission_missing() -> None:
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(EchoTool(required_permissions=frozenset({Permission("admin")})))

    with pytest.raises(ToolPermissionDeniedError):
        await registry.invoke(
            "echo_tool", "1.0.0", {"text": "hi"}, context(roles=frozenset({"viewer"}))
        )

    assert recorder.entries[0].status.value == "denied"


async def test_invoke_rejects_and_records_invalid_input() -> None:
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(EchoTool())

    with pytest.raises(ToolInputValidationError):
        await registry.invoke("echo_tool", "1.0.0", {}, context())  # missing required "text"

    assert recorder.entries[0].status.value == "failed"


async def test_register_rejects_duplicate_name_and_version() -> None:
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(EchoTool())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(EchoTool())
