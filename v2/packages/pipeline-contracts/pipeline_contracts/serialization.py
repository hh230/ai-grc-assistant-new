"""Shared serialization helpers — one place for the to_dict conventions every contract
model repeats: enums serialize as their value, tuples as lists, nested models via their
own `to_dict`, containers recursively.

Deliberately not reflection-magic: each model still declares its own `to_dict`, choosing
exclusions and computed keys explicitly, so custom schemas stay visible at the model. The
helpers only remove the per-field conversion boilerplate.
"""

from __future__ import annotations

from dataclasses import fields
from enum import Enum


def to_plain(value: object) -> object:
    """Convert one value to its plain-JSON shape (recursively)."""
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def dataclass_dict(
    obj: object,
    *,
    exclude: tuple[str, ...] = (),
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """A dataclass's fields as a plain dict, in declaration order. `exclude` drops
    internal fields; `extra` appends/overrides computed keys the schema requires."""
    data: dict[str, object] = {
        f.name: to_plain(getattr(obj, f.name)) for f in fields(obj) if f.name not in exclude  # type: ignore[arg-type]
    }
    if extra:
        data.update(extra)
    return data
