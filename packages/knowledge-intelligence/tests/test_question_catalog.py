"""The real ``/knowledge-catalog`` question set (KI-P1) loads as valid configuration — not
hardcoded logic — via the same loader any future domain/question addition uses, plus unit
tests for the loader's own validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from grc_knowledge_intelligence import KnowledgeDomain, build_catalog, load_questions

_CATALOG_DIR = Path(__file__).resolve().parents[3] / "knowledge-catalog"
_EXPECTED_DOMAINS = {member.value for member in KnowledgeDomain}


def test_every_domain_has_a_catalog_file_and_loads() -> None:
    files = tuple(sorted(_CATALOG_DIR.glob("*.json")))
    assert len(files) == len(_EXPECTED_DOMAINS)

    catalog = build_catalog(files)

    assert len(catalog) == 33  # 11 domains x 3 questions each, per ADR-0025
    assert {question.domain.value for question in catalog} == _EXPECTED_DOMAINS


def test_every_question_id_is_unique_and_namespaced_by_domain() -> None:
    files = tuple(sorted(_CATALOG_DIR.glob("*.json")))
    catalog = build_catalog(files)
    ids = [question.question_id for question in catalog]
    assert len(ids) == len(set(ids))
    for question in catalog:
        assert question.question_id.startswith(f"{question.domain.value}.")


def test_every_question_has_non_empty_text_and_category() -> None:
    files = tuple(sorted(_CATALOG_DIR.glob("*.json")))
    catalog = build_catalog(files)
    for question in catalog:
        assert question.question.strip()
        assert question.category.strip()
        assert question.question.endswith("?")


def test_load_questions_rejects_an_unknown_domain() -> None:
    with pytest.raises(ValueError):
        load_questions(
            {
                "domain": "not-a-real-domain",
                "questions": [
                    {"question_id": "x.1", "category": "c", "question": "What?"},
                ],
            }
        )


def test_load_questions_rejects_an_empty_questions_list() -> None:
    with pytest.raises(ValueError):
        load_questions({"domain": "audit", "questions": []})


def test_build_catalog_rejects_duplicate_question_ids_across_files(tmp_path: Path) -> None:
    duplicate = {
        "domain": "audit",
        "questions": [{"question_id": "audit.dup", "category": "c", "question": "What?"}],
    }
    first_file = tmp_path / "audit_a.json"
    second_file = tmp_path / "audit_b.json"
    first_file.write_text(json.dumps(duplicate), encoding="utf-8")
    second_file.write_text(json.dumps(duplicate), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate question_id"):
        build_catalog([first_file, second_file])
