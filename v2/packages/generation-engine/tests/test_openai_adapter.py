"""The OpenAI adapter (moved from ai-orchestrator): request/response mapping — plus the new
SDK→domain error translation. Exercised through injected fake clients; no SDK, no network."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from generation_engine import OpenAIGenerationProvider
from pipeline_contracts import (
    AuthenticationError,
    GenerationError,
    GenerationProvider,
    InvalidRequest,
    ProviderUnavailable,
    RateLimitError,
)
from pipeline_contracts import TimeoutError as GenerationTimeoutError

from tests.conftest import make_request


class FakeOpenAIClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._error = error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(
            model="gpt-4o-mini-2024",
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="PDPL is the Saudi data protection law."),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=42, completion_tokens=11, total_tokens=53),
        )


def test_adapter_satisfies_the_protocol():
    assert isinstance(OpenAIGenerationProvider(client=FakeOpenAIClient()), GenerationProvider)


def test_openai_adapter_maps_request_and_response():
    client = FakeOpenAIClient()
    provider = OpenAIGenerationProvider(client=client)
    request = make_request(temperature=0.1, max_output_tokens=800)

    answer = provider.generate(request)

    call = client.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["temperature"] == 0.1
    assert call["max_tokens"] == 800
    assert call["messages"] == request.messages()
    assert call["messages"][0]["role"] == "system"
    assert "You are Rasheed." in call["messages"][0]["content"]

    assert answer.text == "PDPL is the Saudi data protection law."
    assert answer.provider == "openai"
    assert answer.model == "gpt-4o-mini-2024"
    assert answer.finish_reason == "stop"
    assert answer.usage == {"prompt_tokens": 42, "completion_tokens": 11, "total_tokens": 53}


def test_openai_adapter_defaults_params_when_absent():
    client = FakeOpenAIClient()
    OpenAIGenerationProvider(client=client).generate(make_request())

    call = client.calls[0]
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 1200


# ── SDK → domain error translation ────────────────────────────────────────────
def _sdk_error(name: str, status: int | None = None) -> Exception:
    exc_type = type(name, (Exception,), {})
    exc = exc_type("simulated")
    if status is not None:
        exc.status_code = status
    return exc


@pytest.mark.parametrize("sdk_name,status,domain", [
    ("AuthenticationError", 401, AuthenticationError),
    ("PermissionDeniedError", 403, AuthenticationError),
    ("RateLimitError", 429, RateLimitError),
    ("APITimeoutError", None, GenerationTimeoutError),
    ("APIConnectionError", None, ProviderUnavailable),
    ("InternalServerError", 500, ProviderUnavailable),
    ("BadRequestError", 400, InvalidRequest),
    ("NotFoundError", 404, InvalidRequest),
])
def test_sdk_errors_become_domain_errors(sdk_name, status, domain):
    provider = OpenAIGenerationProvider(client=FakeOpenAIClient(error=_sdk_error(sdk_name, status)))
    with pytest.raises(domain) as excinfo:
        provider.generate(make_request())
    assert excinfo.value.provider == "openai"
    assert sdk_name in str(excinfo.value)


def test_builtin_timeout_becomes_domain_timeout():
    provider = OpenAIGenerationProvider(client=FakeOpenAIClient(error=TimeoutError("socket")))
    with pytest.raises(GenerationTimeoutError):
        provider.generate(make_request())


def test_unknown_error_becomes_base_generation_error_not_raw():
    provider = OpenAIGenerationProvider(client=FakeOpenAIClient(error=_sdk_error("SomethingNew")))
    with pytest.raises(GenerationError) as excinfo:
        provider.generate(make_request())
    assert type(excinfo.value) is GenerationError
    assert not excinfo.value.retryable


def test_missing_sdk_raises_a_helpful_error():
    if "openai" in sys.modules or _importable("openai"):
        pytest.skip("openai SDK installed in this environment")
    with pytest.raises(ImportError, match=r"generation-engine\[openai\]"):
        OpenAIGenerationProvider()


def _importable(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None
