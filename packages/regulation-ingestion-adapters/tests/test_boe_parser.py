"""Unit tests for the deterministic Board of Experts (laws.boe.gov.sa) page parser:
metadata extraction, chapter/article splitting (never splitting one article across two
sections), amendment attachment, Arabic text preservation, and the no-chapters fallback. Pure
text-in/struct-out — no network, no fixture files, matching this repo's
build-the-minimal-input-at-test-time convention."""

from __future__ import annotations

from grc_regulation_ingestion_adapters import parse_boe_page

_SAMPLE_TEXT = """النظام الأساسي للحكم
Law name
Basic Law of Governance
تاريخ الإصدار
1412/08/27 هـ  الموافق : 01/03/1992 مـ
تاريخ النشر
1412/09/02  هـ الموافق : 06/03/1992 مـ
الحالة
ساري
أدوات إصدار النظام
أمر ملكي رقم أ/90 بتاريخ 27 / 8 / 1412
النظام الأساسي للحكم
الباب الأول :  المبادئ العامة
المادة الأولى
المملكة العربية السعودية، دولة عربية إسلامية، ذات سيادة تامة.
المادة الثانية
عيدا الدولة، هما عيدا الفطر والأضحى، وتقويمها هو التقويم الهجري.
تعديلات المادة
المادة الثانية
عدلت هذه المادة بموجب الأمر الملكي رقم (أ/135) وتاريخ 26 / 9 / 1427 هـ.
"""


def test_extracts_metadata() -> None:
    parsed = parse_boe_page(_SAMPLE_TEXT, name_ar="النظام الأساسي للحكم")

    assert parsed.name_ar == "النظام الأساسي للحكم"
    assert parsed.name_en == "Basic Law of Governance"
    assert parsed.issuance_date_raw == "1412/08/27 هـ  الموافق : 01/03/1992 مـ"
    assert parsed.status_ar == "ساري"
    assert parsed.official_citation == "أمر ملكي رقم أ/90 بتاريخ 27 / 8 / 1412"


def test_splits_chapter_and_articles_without_ever_merging_two_articles() -> None:
    parsed = parse_boe_page(_SAMPLE_TEXT, name_ar="النظام الأساسي للحكم")

    types = [(s.section_type, s.code) for s in parsed.sections]
    assert types == [
        ("chapter", "الأول"),
        ("article", "الأولى"),
        ("article", "الثانية"),
    ]

    chapter = parsed.sections[0]
    assert chapter.title_ar == "المبادئ العامة"

    article_one = parsed.sections[1]
    assert article_one.path == ("الأول",)
    assert article_one.parent_index == 0
    assert article_one.text_ar == "المملكة العربية السعودية، دولة عربية إسلامية، ذات سيادة تامة."
    assert article_one.amendment_note_ar is None


def test_amendment_note_is_attached_to_its_own_article_not_a_new_section() -> None:
    parsed = parse_boe_page(_SAMPLE_TEXT, name_ar="النظام الأساسي للحكم")

    article_two = parsed.sections[2]
    assert article_two.text_ar == "عيدا الدولة، هما عيدا الفطر والأضحى، وتقويمها هو التقويم الهجري."
    assert article_two.amendment_note_ar is not None
    assert "تعديلات المادة" in article_two.amendment_note_ar
    assert "أ/135" in article_two.amendment_note_ar

    # The amendment's own repeated "المادة الثانية" heading must never become a phantom
    # fourth section.
    assert len(parsed.sections) == 3


def test_regulation_with_no_chapters_still_extracts_top_level_articles() -> None:
    text = (
        "Law name\nA Simple Law\n"
        "المادة الأولى\nنص المادة الأولى.\n"
        "المادة الثانية\nنص المادة الثانية.\n"
    )

    parsed = parse_boe_page(text, name_ar="نظام بسيط")

    assert [s.section_type for s in parsed.sections] == ["article", "article"]
    assert parsed.sections[0].path == ()
    assert parsed.sections[0].text_ar == "نص المادة الأولى."
