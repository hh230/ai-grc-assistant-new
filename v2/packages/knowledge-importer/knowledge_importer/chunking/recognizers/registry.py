"""Maps a Document Profile's `recognizer` name to the boundary-detection function that
implements it, for recognizers that take just `lines` and return `Boundary` objects.
Three recognizers are dispatched specially by `engine.py` instead of through this
registry: `policy_procedure` (needs an extra `mode` argument from the profile's
skeleton), and `tabular`/`fallback_window` (they don't fit the generic
line-boundary-with-level model at all — see `chunking/tabular.py` and
`chunking/fallback_window.py`)."""

from __future__ import annotations

from collections.abc import Callable

from knowledge_importer.chunking.recognizers import contract_clause, regulation_article, standard_clause
from knowledge_importer.chunking.recognizers.base import Boundary

LineBoundaryDetector = Callable[[list[tuple[int, str]]], list[Boundary]]

_LINE_BOUNDARY_RECOGNIZERS: dict[str, LineBoundaryDetector] = {
    "standard_clause": standard_clause.detect_boundaries,
    "regulation_article": regulation_article.detect_boundaries,
    "contract_clause": contract_clause.detect_boundaries,
}


def get_line_boundary_recognizer(name: str) -> LineBoundaryDetector | None:
    return _LINE_BOUNDARY_RECOGNIZERS.get(name)
