"""The authored-pack path (ADR 0067).

A pack a practitioner wrote outranks anything a model proposes, so it gets its own loader — with
the generator's model-facing rules dropped and the schema's rules kept, checked here so a bad pack
names its own offending question instead of surfacing a constraint name.
"""

from __future__ import annotations

import json

import pytest

from grc_api.knowledge_seed import (
    AUTHORED_BY_MODEL,
    AuthoredPackGenerator,
    AuthoredPackRejected,
    available_packs,
    load_pack,
)


def test_the_real_estate_pack_loads_and_is_the_one_that_was_authored():
    pack = load_pack("real_estate")
    ids = [q["question_id"] for q in pack["questions"]]
    assert len(ids) == 22
    assert len(set(ids)) == 22
    assert pack["canonical_name_ar"] == "العقارات"


def test_the_five_MULTI_SELECT_questions_survived_the_round_trip():
    """The correction that prompted migration 0016: five questions were registration forms wearing
    a question's clothes, and an option meaning "more than one" recorded THAT several apply while
    losing WHICH."""
    questions = {q["question_id"]: q for q in load_pack("real_estate")["questions"]}
    multi = {qid for qid, q in questions.items() if q["type"] == "multi_select"}
    assert multi == {
        "re_activities_practiced",
        "re_government_platforms",
        "re_governance_documents",
        "re_data_categories",
        "re_pdpl_requirements",
    }
    assert all(len(questions[qid]["options"]) >= 2 for qid in multi)
    # And the smuggled option is gone from the activities question.
    assert "أكثر من نشاط" not in questions["re_activities_practiced"]["options"]


def test_the_two_questions_that_were_MISSING_are_present():
    """Government-platform links and the technical operating model each decide obligations that no
    other question in the pack reaches."""
    questions = {q["question_id"]: q for q in load_pack("real_estate")["questions"]}
    platforms = questions["re_government_platforms"]
    assert platforms["type"] == "multi_select"
    assert any("إيجار" in option for option in platforms["options"])
    assert any("فال" in option for option in platforms["options"])
    assert any("بلدي" in option for option in platforms["options"])
    assert any("نافذ" in option for option in platforms["options"])
    assert any("العدل" in option for option in platforms["options"])

    outsourcing = questions["re_technical_outsourcing"]
    assert any("SaaS" in option for option in outsourcing["options"])


def test_every_question_carries_a_reference_and_a_reason():
    """Both appear side by side in the review console; a question missing either cannot be judged."""
    for question in load_pack("real_estate")["questions"]:
        assert question["references"], question["question_id"]
        assert question["why_we_ask"].strip(), question["question_id"]
        assert question["category"].strip(), question["question_id"]


def test_the_generator_port_returns_the_authored_questions():
    """Same port as the model-backed generator, so the service needs no branch."""
    assert len(AuthoredPackGenerator().generate(industry_slug="real_estate")) == 22


def test_an_unknown_sector_is_refused_by_name():
    with pytest.raises(AuthoredPackRejected, match="no authored pack"):
        load_pack("aerospace")


def test_available_packs_lists_what_exists():
    assert "real_estate" in available_packs()


def test_provenance_says_authored_not_a_model_that_never_ran():
    assert AUTHORED_BY_MODEL == "authored"


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ({"type": "slider"}, "the schema permits"),
        ({"type": "multi_select", "options": ["one"]}, "fewer than 2 options"),
        ({"importance": "urgent"}, "unknown importance"),
        ({"why_we_ask": "  "}, "no why_we_ask"),
        ({"references": []}, "cites no framework"),
        ({"canonical_text_ar": ""}, "no canonical_text_ar"),
    ],
)
def test_a_malformed_pack_names_its_own_question(tmp_path, monkeypatch, mutation, expected):
    """The failure a human reads should say which question is wrong, not which constraint fired."""
    from grc_api import knowledge_seed

    pack = json.loads(
        (knowledge_seed.PACKS_DIR / "real_estate.ar.json").read_text(encoding="utf-8")
    )
    pack["questions"][0].update(mutation)
    (tmp_path / "real_estate.ar.json").write_text(
        json.dumps(pack, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(knowledge_seed, "PACKS_DIR", tmp_path)

    with pytest.raises(AuthoredPackRejected, match=expected) as raised:
        knowledge_seed.load_pack("real_estate")
    assert "re_activities_practiced" in str(raised.value) or "question[0]" in str(raised.value)
