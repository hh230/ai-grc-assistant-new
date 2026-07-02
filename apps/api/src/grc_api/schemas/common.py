"""Shared schema primitives: the response base, the problem model, and the Result unwrapper."""

from __future__ import annotations

from typing import Any, TypeVar

from grc_services.shared.result import Failure, Result
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base for response models. Reads straight from frozen application DTOs by attribute."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ProblemDetail(BaseModel):
    """RFC 9457 problem document (the uniform error shape for every failed request)."""

    type: str
    title: str
    status: int
    code: str
    detail: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    errors: list[Any] | None = None


# Reusable OpenAPI ``responses`` documentation for the common error statuses.
_PROBLEM = {"model": ProblemDetail, "content": {"application/problem+json": {}}}


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Document the given error statuses (plus the always-possible 401) for a route."""
    documented = {401, *statuses}
    return dict.fromkeys(sorted(documented), _PROBLEM)


def unwrap(result: Result[T]) -> T:
    """Return the success value, or raise the application error so it maps to problem+json."""
    if isinstance(result, Failure):
        raise result.error
    return result.value
