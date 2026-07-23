"""Fixtures: a fake `GenerationProvider` that echoes the folded prompt (so we can assert the tool
built a correct `LLMRequest`), plus the **real** `GenerationEngine` wrapping it — proving the tool
plugs into the genuine generation stack, not a mock of it."""

from __future__ import annotations

import pytest
from pipeline_contracts import Answer, GenerationError, LLMRequest, TenantContext


class FakeProvider:
    """Records the last request and returns a canned Answer that reflects the folded messages."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.last_request: LLMRequest | None = None

    @property
    def name(self) -> str:
        return "fake"

    def generate(self, request: LLMRequest) -> Answer:
        self.last_request = request
        if self._fail:
            raise GenerationError("provider is down", provider=self.name)
        user = next((m["content"] for m in request.messages() if m["role"] == "user"), "")
        return Answer(text=f"draft: {user}", provider=self.name, model="fake-1")


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def failing_provider() -> FakeProvider:
    return FakeProvider(fail=True)


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))
