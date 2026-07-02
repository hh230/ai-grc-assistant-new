"""The extractor plugin registry.

Extractors are discovered and resolved through this registry (the plugin entry point). New
extractors — rule-based or AI-assisted, internal or partner — appear by registration; no core
change. A profile names the extractors it wants by reference, and the registry resolves them.
Pure (in-memory); no I/O.
"""
from __future__ import annotations

from .exceptions import DuplicateExtractorError, UnknownExtractorError
from .ports import ExtractorDescriptor, ExtractorPort
from .profiles import ExtractionProfile, ExtractorRef


class ExtractorRegistry:
    """In-memory registry of extractor plugins, keyed by (name, version)."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], ExtractorPort] = {}
        self._latest: dict[str, ExtractorPort] = {}

    def register(self, extractor: ExtractorPort) -> None:
        descriptor = extractor.descriptor
        if descriptor.key in self._by_key:
            raise DuplicateExtractorError(
                f"Extractor already registered: {descriptor.name} v{descriptor.version}"
            )
        self._by_key[descriptor.key] = extractor
        # Last registration for a name is treated as its latest.
        self._latest[descriptor.name] = extractor

    def get(self, name: str, version: str | None = None) -> ExtractorPort:
        if version is not None:
            extractor = self._by_key.get((name, version))
            if extractor is None:
                raise UnknownExtractorError(f"No extractor {name} v{version}")
            return extractor
        latest = self._latest.get(name)
        if latest is None:
            raise UnknownExtractorError(f"No extractor registered with name {name}")
        return latest

    def resolve(self, profile: ExtractionProfile) -> tuple[ExtractorPort, ...]:
        """Resolve, in order, the extractors a profile references."""
        return tuple(self._resolve_ref(ref) for ref in profile.extractor_refs)

    def _resolve_ref(self, ref: ExtractorRef) -> ExtractorPort:
        return self.get(ref.name, ref.version)

    def descriptors(self) -> tuple[ExtractorDescriptor, ...]:
        return tuple(extractor.descriptor for extractor in self._by_key.values())
