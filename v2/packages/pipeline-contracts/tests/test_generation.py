"""The generation port and its error model.

`retryable` is the whole point of the hierarchy: the Generation Engine reads it to decide
whether to try again, so an error classified wrongly either burns the budget retrying a
call that can never succeed, or gives up on one that would have.
"""

from __future__ import annotations

import builtins

from pipeline_contracts import (
    Answer,
    AuthenticationError,
    GenerationError,
    GenerationProvider,
    InvalidRequest,
    LLMRequest,
    ProviderUnavailable,
    RateLimitError,
    TimeoutError,
)


class StubProvider:
    """A structural implementation — no base class, no registration, no SDK."""

    @property
    def name(self) -> str:
        return "stub"

    def generate(self, request: LLMRequest) -> Answer:
        return Answer(text="ok", provider=self.name)


def test_a_provider_satisfies_the_port_structurally():
    assert isinstance(StubProvider(), GenerationProvider)


def test_something_without_generate_is_not_a_provider():
    class NotAProvider:
        name = "nope"

    assert not isinstance(NotAProvider(), GenerationProvider)


def test_every_domain_error_is_a_generation_error():
    for error in (AuthenticationError, InvalidRequest, RateLimitError, TimeoutError,
                  ProviderUnavailable):
        assert issubclass(error, GenerationError)


def test_transient_failures_are_retryable_and_permanent_ones_are_not():
    assert RateLimitError("throttled").retryable is True
    assert TimeoutError("too slow").retryable is True
    assert ProviderUnavailable("503").retryable is True
    assert AuthenticationError("bad key").retryable is False
    assert InvalidRequest("malformed").retryable is False
    assert GenerationError("unknown").retryable is False  # unclassified: never auto-retried


def test_an_error_carries_the_provider_that_raised_it_for_audit():
    error = RateLimitError("throttled", provider="openai")
    assert error.provider == "openai"
    assert str(error) == "throttled"


def test_provider_defaults_to_empty_rather_than_none():
    assert RateLimitError("throttled").provider == ""


def test_the_domain_timeout_is_not_the_builtin():
    """The name is deliberately re-used, so a caller catching the builtin would miss ours —
    it is a `GenerationError` with retry semantics and a provider, not a bare timeout."""
    assert TimeoutError is not builtins.TimeoutError
    assert not issubclass(TimeoutError, builtins.TimeoutError)
