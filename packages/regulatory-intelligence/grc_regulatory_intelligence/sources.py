"""Regulatory sources as configuration, not hardcoded logic (CLAUDE.md §13's "frameworks are
data, not code" applied to regulators: onboarding a new regulator is a data change, never an
architectural one). ``RegulatorySourceRegistry`` is the in-memory catalog every crawler run
reads from — it mirrors ``grc_framework_engine.FrameworkCatalog``'s role for frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceType(str, Enum):
    """The shape of a regulatory source's publishing surface."""

    WEBSITE = "website"
    RSS_FEED = "rss_feed"
    DOCUMENT_LIBRARY = "document_library"
    API = "api"


class PollingFrequency(str, Enum):
    """How often a source should be polled — the polite-crawling cadence. `MANUAL` sources
    are never auto-scheduled."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MANUAL = "manual"


@dataclass(frozen=True)
class RegulatorySource:
    """One configured regulatory source."""

    source_id: str
    regulator_name: str
    jurisdiction: str  # ISO 3166-1 alpha-2 country code, e.g. "SA"
    language: str  # BCP-47 primary content language, e.g. "ar"
    base_url: str
    source_type: SourceType
    polling_frequency: PollingFrequency
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("RegulatorySource.source_id must not be empty")
        if not self.regulator_name.strip():
            raise ValueError("RegulatorySource.regulator_name must not be empty")
        if not self.jurisdiction.strip():
            raise ValueError("RegulatorySource.jurisdiction must not be empty")
        if not self.language.strip():
            raise ValueError("RegulatorySource.language must not be empty")
        if not self.base_url.strip():
            raise ValueError("RegulatorySource.base_url must not be empty")


class RegulatorySourceRegistry:
    """An in-memory catalog of configured regulatory sources. Loading sources from local
    JSON config files is a thin infrastructure concern layered on top — see
    ``source_config.py`` (mirrors ``grc_framework_engine``'s loader/files split)."""

    def __init__(self, sources: tuple[RegulatorySource, ...] = ()) -> None:
        self._sources: dict[str, RegulatorySource] = {}
        for source in sources:
            self.register(source)

    def register(self, source: RegulatorySource) -> None:
        if source.source_id in self._sources:
            raise ValueError(f"a source is already registered for {source.source_id!r}")
        self._sources[source.source_id] = source

    def get(self, source_id: str) -> RegulatorySource:
        try:
            return self._sources[source_id]
        except KeyError as exc:
            raise KeyError(f"no regulatory source registered for {source_id!r}") from exc

    def list_all(self) -> tuple[RegulatorySource, ...]:
        return tuple(self._sources.values())

    def list_enabled(self) -> tuple[RegulatorySource, ...]:
        return tuple(source for source in self._sources.values() if source.enabled)
