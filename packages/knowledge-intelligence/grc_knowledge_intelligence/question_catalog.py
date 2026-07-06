"""Read the Knowledge Question Generator's catalog from local JSON config files (mirrors
``grc_regulatory_intelligence.source_config``'s role for regulatory sources and
``grc_framework_engine.files``'s role for frameworks — CLAUDE.md §13: configuration, not
code). Questions live under ``/knowledge-catalog/<domain>.json``.

Only the standard library (``json``, ``pathlib``) is used, and this module never assumes a
repo layout itself — the caller resolves and passes in the files to load (the same contract
``grc_regulatory_intelligence.source_config.build_registry`` already established), so this
package stays usable from any working directory or test harness.

Canonical file schema (a parsed mapping)::

    {
      "domain": "vendor_management",
      "questions": [
        {
          "question_id": "vendor_management.contract_clauses",
          "category": "contract_requirements",
          "question": "What clauses should exist in a vendor contract?"
        }
      ]
    }
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from .enums import KnowledgeDomain
from .models import KnowledgeQuestion


def _require_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or empty required field {key!r}")
    return value


def load_questions(data: Mapping[str, object]) -> tuple[KnowledgeQuestion, ...]:
    """Validate and translate one parsed catalog file into its ``KnowledgeQuestion``s."""
    domain = KnowledgeDomain(_require_str(data, "domain"))
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("catalog file must contain a non-empty 'questions' list")

    questions: list[KnowledgeQuestion] = []
    for raw in raw_questions:
        if not isinstance(raw, Mapping):
            raise ValueError("each entry in 'questions' must be an object")
        questions.append(
            KnowledgeQuestion(
                question_id=_require_str(raw, "question_id"),
                question=_require_str(raw, "question"),
                domain=domain,
                category=_require_str(raw, "category"),
            )
        )
    return tuple(questions)


def load_questions_file(path: Path) -> tuple[KnowledgeQuestion, ...]:
    if path.suffix.lower() != ".json":
        raise ValueError(
            f"Unsupported catalog file format {path.suffix!r} for {path}; expected '.json'"
        )
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError(f"{path} must contain an object at the top level")
    return load_questions(parsed)


def build_catalog(question_files: Iterable[Path] = ()) -> tuple[KnowledgeQuestion, ...]:
    """Build the full question catalog by loading every given catalog file. Raises
    ``ValueError`` if two files declare the same ``question_id`` — ``question_id`` is an
    append-only key (see ``/knowledge-catalog/README.md``), never one two questions share."""
    questions: list[KnowledgeQuestion] = []
    seen_ids: set[str] = set()
    for path in question_files:
        for question in load_questions_file(path):
            if question.question_id in seen_ids:
                raise ValueError(f"duplicate question_id: {question.question_id!r}")
            seen_ids.add(question.question_id)
            questions.append(question)
    return tuple(questions)
