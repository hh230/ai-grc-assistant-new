"""Typed accessors over a connector's ``ConnectorResult.data`` — so jobs read evidence cleanly.

Jobs orchestrate over connector data (plain ``Mapping[str, object]``); these helpers pull typed rows
and fields out of it without scattering ``isinstance`` checks through every job.
"""

from __future__ import annotations

from collections.abc import Mapping

from devteam_organization.connectors import ConnectorResult


def rows(result: ConnectorResult, key: str) -> list[Mapping[str, object]]:
    value = result.data.get(key)
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def str_list(result: ConnectorResult, key: str) -> list[str]:
    value = result.data.get(key)
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def count(result: ConnectorResult, key: str, default: int = 0) -> int:
    value = result.data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def field_str(row: Mapping[str, object], key: str, default: str = "") -> str:
    value = row.get(key)
    return value if isinstance(value, str) else default


def field_bool(row: Mapping[str, object], key: str) -> bool:
    return row.get(key) is True


def field_int(row: Mapping[str, object], key: str, default: int | None = None) -> int | None:
    value = row.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else default
