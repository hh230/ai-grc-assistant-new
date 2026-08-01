"""Filesystem connector — read-only inspection of configured folders (§11).

Lists entries of configured folders so a job (e.g. GRC checking a policies dir) can see what
is present. **Read-only**: it only lists; never opens/writes/deletes. No folders configured ⇒
Unavailable.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devteam_protocol import AgentRole

from devteam_organization.connectors.framework import ConnectorResult, ConnectorType

_MAX_FILES = 100


class FilesystemConnector:
    id = "filesystem"
    name = "Filesystem"
    type = ConnectorType.FILESYSTEM
    owner = AgentRole.GRC_EXPERT

    def __init__(self, folders: Sequence[str], *, repo_root: Path | str = ".") -> None:
        self._folders = tuple(folders)
        self._root = Path(repo_root)

    @property
    def enabled(self) -> bool:
        return bool(self._folders)

    def fetch(self) -> ConnectorResult:
        if not self._folders:
            return ConnectorResult.unavailable("no folders configured")
        rows: list[dict[str, object]] = []
        for folder in self._folders:
            path = Path(folder) if Path(folder).is_absolute() else self._root / folder
            if not path.exists():
                rows.append({"path": folder, "exists": False, "file_count": 0, "files": []})
                continue
            try:
                names = sorted(entry.name for entry in path.iterdir())
            except OSError as exc:
                rows.append({"path": folder, "exists": True, "error": repr(exc)})
                continue
            rows.append(
                {
                    "path": folder,
                    "exists": True,
                    "file_count": len(names),
                    "files": names[:_MAX_FILES],
                }
            )
        return ConnectorResult.okay({"folders": rows})
