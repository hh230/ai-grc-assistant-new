"""The Claude / Gemini / Ollama adapters: request/response mapping and SDK→domain error
translation, all through injected fake clients — no SDK, no network. Same contract the
OpenAI adapter is held to."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from generation_engine import (
    ClaudeGenerationProvider,
    GeminiGenerationProvider,
    OllamaGenerationProvider,
)
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

ANSWER_TEXT = "PDPL is the Saudi data protection law."


def _sdk_error(name: str, status: int | None = None, *, attr: str = "status_code") -> Exception:
    exc = type(name, (Exception,), {})("simulated")
    if status is not None:
        setattr(exc, attr, status)
    return exc


# ── Claude ────────────────────────────────────────────────────────────────────
class FakeAnthropic:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._error = error
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(
            model="claude-opus-4-8-20260101",
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=ANSWER_TEXT)],
            usage=SimpleNamespace(input_tokens=42, output_tokens=11),
        )


def test_claude_satisfies_the_protocol():
    assert isinstance(ClaudeGenerationProvider(client=FakeAnthropic()), GenerationProvider)


def test_claude_maps_request_and_response():
    client = FakeAnthropic()
    provider = ClaudeGenerationProvider(client=client)
    answer = provider.generate(make_request(temperature=0.1, max_output_tokens=800))

    call = client.calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["temperature"] == 0.1
    assert call["max_tokens"] == 800
    # system prompt is lifted out of the chat turns into the top-level `system` arg
    assert "You are Rasheed." in call["system"]
    assert all(m["role"] != "system" for m in call["messages"])
    assert call["messages"][-1]["role"] == "user"

    assert answer.provider == "claude"
    assert answer.text == ANSWER_TEXT
    assert answer.model == "claude-opus-4-8-20260101"
    assert answer.finish_reason == "end_turn"
    assert answer.usage == {"prompt_tokens": 42, "completion_tokens": 11, "total_tokens": 53}


def test_claude_defaults_params_when_absent():
    client = FakeAnthropic()
    ClaudeGenerationProvider(client=client).generate(make_request())
    assert client.calls[0]["temperature"] == 0.2
    assert client.calls[0]["max_tokens"] == 1200


# ── Gemini ────────────────────────────────────────────────────────────────────
class FakeGemini:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._error = error
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(
            text=ANSWER_TEXT,
            model_version="gemini-2.5-pro-002",
            candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))],
            usage_metadata=SimpleNamespace(
                prompt_token_count=30, candidates_token_count=9, total_token_count=39
            ),
        )


def test_gemini_satisfies_the_protocol():
    assert isinstance(GeminiGenerationProvider(client=FakeGemini()), GenerationProvider)


def test_gemini_maps_request_and_response():
    client = FakeGemini()
    provider = GeminiGenerationProvider(client=client)
    answer = provider.generate(make_request(temperature=0.3, max_output_tokens=500))

    call = client.calls[0]
    assert call["model"] == "gemini-2.5-pro"
    assert call["config"]["temperature"] == 0.3
    assert call["config"]["max_output_tokens"] == 500
    assert "You are Rasheed." in call["config"]["system_instruction"]
    assert "What is PDPL?" in call["contents"]

    assert answer.provider == "gemini"
    assert answer.text == ANSWER_TEXT
    assert answer.model == "gemini-2.5-pro-002"
    assert answer.finish_reason == "STOP"
    assert answer.usage == {"prompt_tokens": 30, "completion_tokens": 9, "total_tokens": 39}


# ── Ollama ────────────────────────────────────────────────────────────────────
class FakeOllama:
    def __init__(self, error: Exception | None = None, *, as_dict: bool = False) -> None:
        self.calls: list[dict] = []
        self._error = error
        self._as_dict = as_dict

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        if self._as_dict:  # older SDK shape
            return {
                "model": "llama3.1", "done_reason": "stop",
                "message": {"content": ANSWER_TEXT},
                "prompt_eval_count": 20, "eval_count": 7,
            }
        return SimpleNamespace(  # typed ChatResponse shape
            model="llama3.1", done_reason="stop",
            message=SimpleNamespace(content=ANSWER_TEXT),
            prompt_eval_count=20, eval_count=7,
        )


def test_ollama_satisfies_the_protocol():
    assert isinstance(OllamaGenerationProvider(client=FakeOllama()), GenerationProvider)


@pytest.mark.parametrize("as_dict", [False, True])
def test_ollama_maps_request_and_response_across_sdk_shapes(as_dict):
    client = FakeOllama(as_dict=as_dict)
    provider = OllamaGenerationProvider(client=client)
    answer = provider.generate(make_request(temperature=0.0, max_output_tokens=256))

    call = client.calls[0]
    assert call["model"] == "llama3.1"
    assert call["options"]["temperature"] == 0.0
    assert call["options"]["num_predict"] == 256
    assert call["messages"][0]["role"] == "system"

    assert answer.provider == "ollama"
    assert answer.text == ANSWER_TEXT
    assert answer.model == "llama3.1"
    assert answer.finish_reason == "stop"
    assert answer.usage == {"prompt_tokens": 20, "completion_tokens": 7, "total_tokens": 27}


# ── shared error translation ──────────────────────────────────────────────────
PROVIDERS = {
    "claude": (ClaudeGenerationProvider, FakeAnthropic),
    "gemini": (GeminiGenerationProvider, FakeGemini),
    "ollama": (OllamaGenerationProvider, FakeOllama),
}


@pytest.mark.parametrize("provider_name", ["claude", "gemini", "ollama"])
@pytest.mark.parametrize("sdk_name,status,domain", [
    ("AuthenticationError", 401, AuthenticationError),
    ("RateLimitError", 429, RateLimitError),
    ("APITimeoutError", 408, GenerationTimeoutError),
    ("InternalServerError", 503, ProviderUnavailable),
    ("BadRequestError", 400, InvalidRequest),
])
def test_sdk_errors_become_domain_errors(provider_name, sdk_name, status, domain):
    cls, fake = PROVIDERS[provider_name]
    provider = cls(client=fake(error=_sdk_error(sdk_name, status)))
    with pytest.raises(domain) as excinfo:
        provider.generate(make_request())
    assert excinfo.value.provider == provider_name


def test_gemini_translates_status_on_code_attribute():
    # google-genai carries the HTTP status on `.code`, not `.status_code`
    provider = GeminiGenerationProvider(client=FakeGemini(error=_sdk_error("ClientError", 429, attr="code")))
    with pytest.raises(RateLimitError):
        provider.generate(make_request())


def test_unknown_error_becomes_base_generation_error_not_raw():
    provider = ClaudeGenerationProvider(client=FakeAnthropic(error=_sdk_error("SomethingNew")))
    with pytest.raises(GenerationError) as excinfo:
        provider.generate(make_request())
    assert type(excinfo.value) is GenerationError
    assert not excinfo.value.retryable


def test_domain_error_from_double_passes_through_untranslated():
    provider = OllamaGenerationProvider(client=FakeOllama(error=RateLimitError("throttled", provider="ollama")))
    with pytest.raises(RateLimitError):
        provider.generate(make_request())


@pytest.mark.parametrize("cls", [ClaudeGenerationProvider, GeminiGenerationProvider, OllamaGenerationProvider])
def test_missing_sdk_raises_a_helpful_error(cls):
    sdk = {"ClaudeGenerationProvider": "anthropic",
           "GeminiGenerationProvider": "google",
           "OllamaGenerationProvider": "ollama"}[cls.__name__]
    if _importable(sdk):
        pytest.skip(f"{sdk} SDK installed in this environment")
    with pytest.raises(ImportError, match=r"generation-engine\["):
        cls()


def _importable(name: str) -> bool:
    import importlib.util

    if name in sys.modules:
        return True
    return importlib.util.find_spec(name) is not None
