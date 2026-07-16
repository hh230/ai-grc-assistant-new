"""Document Profile catalog + assignment (architecture doc §2, §2.1, §2.2).

A Document Profile is data: which Recognizer runs, what skeleton to validate confidence
against, whether the source is expected bilingual, and default fallback-windowing
parameters. Assignment resolves in priority order: explicit override (a curator's
decision) > format override (`.xlsx` is structurally tabular regardless of category) >
category-level default (the zero-cost fallback) > unmapped (the caller falls through to
the sentence-aware fallback window rather than guessing a genre).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentProfile:
    profile_id: str
    display_name: str
    description: str
    recognizer: str
    skeleton: dict[str, object]
    language_handling: str
    fallback_windowing: dict[str, int]


@dataclass(frozen=True)
class ProfileAssignment:
    profile_id: str | None
    source: str  # "explicit" | "format_override" | "category_default" | "unmapped"


@dataclass(frozen=True)
class ProfileCatalog:
    profiles: dict[str, DocumentProfile]
    category_defaults: dict[str, str]
    format_overrides: dict[str, str]
    explicit_overrides: dict[str, str]

    def resolve(self, *, document_id: str, category: str, extension: str) -> ProfileAssignment:
        override = self.explicit_overrides.get(document_id)
        if override is not None:
            return ProfileAssignment(profile_id=override, source="explicit")

        format_profile = self.format_overrides.get(extension.lower().lstrip("."))
        if format_profile is not None:
            return ProfileAssignment(profile_id=format_profile, source="format_override")

        # Category matching is whitespace-insensitive: real library folders have been
        # observed with stray leading/trailing spaces (e.g. " COBIT") that Phase 1
        # faithfully preserves on the manifest — matching should not be that brittle.
        default_profile = self.category_defaults.get(category.strip())
        if default_profile is not None:
            return ProfileAssignment(profile_id=default_profile, source="category_default")

        return ProfileAssignment(profile_id=None, source="unmapped")

    def get(self, profile_id: str) -> DocumentProfile:
        return self.profiles[profile_id]


def load_profile_catalog(path: Path) -> ProfileCatalog:
    raw = json.loads(path.read_text(encoding="utf-8"))
    profiles = {
        profile_id: DocumentProfile(
            profile_id=profile_id,
            display_name=entry["display_name"],
            description=entry["description"],
            recognizer=entry["recognizer"],
            skeleton=entry.get("skeleton", {}),
            language_handling=entry.get("language_handling", "monolingual"),
            fallback_windowing=entry.get(
                "fallback_windowing", {"window_chars": 1200, "overlap_chars": 150}
            ),
        )
        for profile_id, entry in raw["profiles"].items()
    }
    return ProfileCatalog(
        profiles=profiles,
        category_defaults=raw.get("category_defaults", {}),
        format_overrides=raw.get("format_overrides", {}),
        explicit_overrides=raw.get("explicit_overrides", {}),
    )
