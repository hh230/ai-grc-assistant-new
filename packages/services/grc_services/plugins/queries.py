"""Queries for the Plugin Management capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.shared.identifiers import PluginId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetPlugin(Query):
    plugin_id: PluginId


@dataclass(frozen=True, kw_only=True)
class ListPlugins(Query):
    pass
