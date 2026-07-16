"""Recursive discovery of supported files under `knowledge/library/`."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx", ".txt", ".md"})


@dataclass(frozen=True)
class DiscoveredFile:
    path: Path
    category: str
    relative_path: str


def discover_library(library_root: Path) -> Iterator[DiscoveredFile]:
    """Walks every file under `library_root`, yielding one `DiscoveredFile` per file whose
    extension is in `SUPPORTED_EXTENSIONS`. `category` is the first path segment under
    `library_root` — the category folder (`iso`, `saudi-regulations`, ...) — regardless of
    how deeply the file itself is nested beneath it, so a future subfolder within a
    category never needs a pipeline change. Files are yielded in a stable (sorted) order
    so pipeline output is reproducible run to run."""
    if not library_root.is_dir():
        return
    for path in sorted(library_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        relative = path.relative_to(library_root)
        category = relative.parts[0] if relative.parts else ""
        yield DiscoveredFile(path=path, category=category, relative_path=relative.as_posix())
