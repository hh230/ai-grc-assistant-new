"""Result types for use-case outcomes.

Handlers raise `ApplicationError` for failures; the message-bus boundary converts those
into a `Failure` so callers can choose between exception-style and functional-style error
handling. `Result[T]` is the public return type of the buses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar, Union

from .exceptions import ApplicationError

T = TypeVar("T")


@dataclass(frozen=True)
class Success(Generic[T]):
    value: T
    is_success: ClassVar[bool] = True


@dataclass(frozen=True)
class Failure:
    error: ApplicationError
    is_success: ClassVar[bool] = False


Result = Union[Success[T], Failure]


def ok(value: T) -> Success[T]:
    return Success(value)


def fail(error: ApplicationError) -> Failure:
    return Failure(error)
