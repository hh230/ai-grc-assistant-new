"""Runtime configuration defaults for the importer CLI.

The external Knowledge Library is the single source of truth for documents; it lives
outside the git repository and is never modified, moved, renamed, or copied by this
package. `DEFAULT_LIBRARY_DIR` below is only a *default* for local development — every
run can point elsewhere via `--library-dir`, so the importer is portable across machines
and future deployments without editing code or setting an environment variable.

`v2/knowledge/library/` is kept as a placeholder for future use or ad-hoc testing, but
nothing in this package depends on it or falls back to it.
"""

from __future__ import annotations

from pathlib import Path

_V2_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_LIBRARY_DIR = Path("/Users/mohamedalsayyar/Documents/قاعدة بيانات مشروع Ai GRC")
DEFAULT_MANIFESTS_DIR = _V2_ROOT / "knowledge" / "manifests"
DEFAULT_IMPORTS_DIR = _V2_ROOT / "knowledge" / "imports"
DEFAULT_CHUNKS_DIR = _V2_ROOT / "knowledge" / "chunks"
DEFAULT_EMBEDDINGS_DIR = _V2_ROOT / "knowledge" / "embeddings"
DEFAULT_PROFILES_CATALOG = _V2_ROOT / "knowledge" / "profiles" / "document_profiles.json"
