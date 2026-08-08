"""The Knowledge Pack validator (`lint_pack`).

Written after three authored packs shipped the same defect and were each corrected by hand. The
rules here are those corrections, made mechanical — plus one the hand review could never have
caught, because it produces no symptom anywhere.
"""

import json

import pytest

from grc_api import knowledge_seed
from grc_api.knowledge_seed import Finding, lint_pack, reachable_slugs

GOOD_QUESTION = {
    "question_id": "xx_licence",
    "canonical_text_ar": "هل تمتلك المنشأة ترخيصاً سارياً لمزاولة النشاط؟",
    "type": "enum",
    "options": ["نعم", "لا"],
    "required": True,
    "category": "licensing",
    "importance": "high",
    "why_we_ask": "الترخيص شرط لمزاولة النشاط.",
    "evidence_required": ["الترخيص"],
    "references": [{"framework": "نظام السجل التجاري", "clause": "القيد"}],
}


def _write(tmp_path, monkeypatch, slug="real_estate", **overrides):
    pack = {"industry_slug": slug, "canonical_name_ar": "قطاع", "questions": [dict(GOOD_QUESTION)]}
    pack.update(overrides)
    (tmp_path / f"{slug}.ar.json").write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(knowledge_seed, "PACKS_DIR", tmp_path)
    return pack


def errors(findings: list[Finding]) -> list[str]:
    return [str(f) for f in findings if f.severity == "error"]


def warnings(findings: list[Finding]) -> list[str]:
    return [str(f) for f in findings if f.severity == "warning"]


def test_a_clean_pack_reports_nothing(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)
    assert lint_pack("real_estate") == []


def test_a_slug_no_customer_can_choose_is_an_error(tmp_path, monkeypatch):
    """The failure with no symptom. A pack for a sector the interview does not offer imports,
    approves, publishes and activates without a single complaint — and then reaches nobody, because
    no customer can select a sector they are never shown. Nothing downstream would ever say so."""
    _write(tmp_path, monkeypatch, slug="agriculture")
    problems = errors(lint_pack("agriculture"))
    assert any("no customer can ever be routed" in p for p in problems)


def test_every_shipped_sector_is_reachable():
    """Guards the three live packs against the same silent failure."""
    reachable = reachable_slugs()
    assert reachable, "the interview's primary_activity options could not be read"
    for slug in ("real_estate", "legal_services", "marketing_advertising"):
        assert slug in reachable


def test_single_choice_offering_more_than_one_is_a_warning(tmp_path, monkeypatch):
    """The defect all three authored packs shipped: an enum cannot express multiplicity, so an
    option meaning "several apply" records THAT while losing WHICH."""
    q = dict(GOOD_QUESTION, options=["جهة واحدة", "نعم، أكثر من جهة"])
    _write(tmp_path, monkeypatch, questions=[q])
    assert any("several apply while losing WHICH" in w for w in warnings(lint_pack("real_estate")))


def test_a_quantity_is_not_a_multiplicity(tmp_path, monkeypatch):
    """`أكثر من 70%` is a quantity. The first version of this check could not tell the two apart and
    reported three findings against the real-estate pack, two of them wrong — which is why the rule
    warns rather than blocks."""
    q = dict(GOOD_QUESTION, options=["أقل من 70%", "أغلب العقود موثّقة (أكثر من 70%)"])
    _write(tmp_path, monkeypatch, questions=[q])
    assert warnings(lint_pack("real_estate")) == []


def test_multi_select_may_say_it(tmp_path, monkeypatch):
    """Only single-choice is at fault — a multi_select expresses multiplicity by construction."""
    q = dict(GOOD_QUESTION, type="multi_select", options=["أ", "ب", "مزيج"])
    _write(tmp_path, monkeypatch, questions=[q])
    assert warnings(lint_pack("real_estate")) == []


def test_a_malformed_question_id_is_an_error(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, questions=[dict(GOOD_QUESTION, question_id="Licence Check")])
    assert any("question_id must look like" in e for e in errors(lint_pack("real_estate")))


def test_a_repeated_regulatory_reference_is_an_error(tmp_path, monkeypatch):
    ref = {"framework": "نظام السجل التجاري", "clause": "القيد"}
    _write(tmp_path, monkeypatch, questions=[dict(GOOD_QUESTION, references=[ref, dict(ref)])])
    assert any("twice" in e for e in errors(lint_pack("real_estate")))


def test_a_repeated_option_is_an_error(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, questions=[dict(GOOD_QUESTION, options=["نعم", "نعم"])])
    assert any("twice" in e for e in errors(lint_pack("real_estate")))


def test_the_same_question_asked_twice_is_a_warning(tmp_path, monkeypatch):
    """A warning, not an error: the measure is similarity of wording, and two genuinely different
    questions on one subject can score high. A person decides."""
    twin = dict(GOOD_QUESTION, question_id="xx_licence_again",
                canonical_text_ar="هل تمتلك المنشاه ترخيصا ساريا لمزاوله النشاط؟")
    _write(tmp_path, monkeypatch, questions=[dict(GOOD_QUESTION), twin])
    assert any("alike" in w for w in warnings(lint_pack("real_estate")))


def test_every_problem_is_reported_not_just_the_first(tmp_path, monkeypatch):
    """`load_pack` raises on the first error because a caller about to import needs a decision. An
    author needs the whole list, so one pass of edits fixes everything."""
    broken = dict(GOOD_QUESTION, question_id="Bad Id", references=[])
    _write(tmp_path, monkeypatch, questions=[broken])
    assert len(errors(lint_pack("real_estate"))) >= 2


def test_the_shipped_packs_have_no_errors():
    """The three live packs, linted as they stand on disk."""
    for slug in ("real_estate", "legal_services", "marketing_advertising"):
        assert errors(lint_pack(slug)) == [], slug


@pytest.mark.parametrize("slug", ["real_estate", "legal_services", "marketing_advertising"])
def test_describe_packs_reports_warnings_beside_an_importable_pack(slug):
    described = {d["industry_slug"]: d for d in knowledge_seed.describe_packs()}[slug]
    assert described["problem"] is None
    assert isinstance(described["warnings"], list)


def test_a_single_choice_question_whose_wording_asks_for_several(tmp_path, monkeypatch):
    """The second shape of the defect, found in the IT pack. No offending option existed — the
    author listed co-occurring facts under a single-choice type, and the first rule saw nothing
    because there was nothing to see: the offence was the TYPE, not an option."""
    q = dict(GOOD_QUESTION,
             canonical_text_ar="هل تقدم المنشأة أياً من الخدمات التالية: الحوسبة السحابية أو الأمن السيبراني؟",
             options=["حوسبة سحابية", "أمن سيبراني"])
    _write(tmp_path, monkeypatch, questions=[q])
    assert any("asks which of several apply" in w for w in warnings(lint_pack("real_estate")))


def test_several_separate_yes_options_in_one_single_choice_question(tmp_path, monkeypatch):
    """The other tell: separate 'نعم' answers are what separate checkboxes look like when somebody
    has flattened them into one list."""
    q = dict(GOOD_QUESTION, options=["نعم - جهات حكومية", "نعم - جهات مالية", "نعم - بنى تحتية", "لا"])
    _write(tmp_path, monkeypatch, questions=[q])
    assert any("separate 'نعم' answers" in w for w in warnings(lint_pack("real_estate")))


def test_a_plain_yes_no_question_is_not_flagged(tmp_path, monkeypatch):
    """The rule must not fire on an ordinary question — one 'نعم' is not a list of yeses."""
    q = dict(GOOD_QUESTION, options=["نعم", "لا"])
    _write(tmp_path, monkeypatch, questions=[q])
    assert warnings(lint_pack("real_estate")) == []


def test_a_pair_of_yes_options_is_a_maturity_distinction_not_a_list(tmp_path, monkeypatch):
    """The calibration that earned the threshold. At two, the rule fired on six questions across
    four packs and was right about roughly one — "نعم مع ضوابط" / "نعم دون ضوابط" is one answer or
    the other, not both. Three or more is a list of mechanisms a customer can genuinely use at once.
    """
    q = dict(GOOD_QUESTION, options=["نعم، مع تقييم موثق", "نعم، دون تقييم", "لا"])
    _write(tmp_path, monkeypatch, questions=[q])
    assert warnings(lint_pack("real_estate")) == []


def test_one_question_with_both_tells_is_reported_once(tmp_path, monkeypatch):
    """A question carrying an "أكثر من" option AND a list of yeses has one problem, not two.
    Saying it twice makes a reviewer trust the whole list less."""
    q = dict(GOOD_QUESTION,
             options=["نعم - أ", "نعم - ب", "نعم، أكثر من جهة", "لا"])
    _write(tmp_path, monkeypatch, questions=[q])
    assert len(warnings(lint_pack("real_estate"))) == 1


def test_the_three_arabic_spellings_of_the_same_phrase_all_count(tmp_path, monkeypatch):
    """`أي من` was missing until the e-commerce pack used it twice and passed clean. Arabic writes
    this phrase three ways depending on the case ending and whether the tanween is typed; a list
    carrying one spelling silently covers one third of the authors."""
    for spelling in ("أي من", "أياً من", "أيا من"):
        q = dict(GOOD_QUESTION,
                 canonical_text_ar=f"هل تطبقون {spelling} الضوابط التالية؟",
                 options=["ضابط أ", "ضابط ب"])
        _write(tmp_path, monkeypatch, questions=[q])
        assert warnings(lint_pack("real_estate")), spelling
