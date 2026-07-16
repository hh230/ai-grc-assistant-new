from __future__ import annotations

from knowledge_importer.chunking.recognizers import contract_clause, policy_procedure, regulation_article, standard_clause
from knowledge_importer.chunking.text_lines import split_into_lines


def _lines(text: str) -> list[tuple[int, str]]:
    return split_into_lines(text)


def test_standard_clause_recognizes_iso_style_nesting() -> None:
    text = (
        "4 Context of the organization\n"
        "Lead text.\n"
        "4.1 Understanding the organization\n"
        "Body.\n"
        "4.2 Understanding needs\n"
        "Body.\n"
        "5 Leadership\n"
        "Body.\n"
        "5.1 Policies for information security\n"  # Annex-A-style restart, same code as a real clause elsewhere
        "Body.\n"
    )
    boundaries = standard_clause.detect_boundaries(_lines(text))
    codes = [b.code for b in boundaries]
    assert codes == ["4", "4.1", "4.2", "5", "5.1"]
    levels = {b.code: b.level for b in boundaries}
    assert levels["4"] == 1
    assert levels["4.1"] == 2
    assert levels["5"] == 1
    assert levels["5.1"] == 2


def test_standard_clause_recognizes_nist_control_enhancement_nesting() -> None:
    text = "AC-2 Account Management\nBody.\nAC-2(1) Automated System Account Management\nBody.\nAC-3 Access Enforcement\nBody.\n"
    boundaries = standard_clause.detect_boundaries(_lines(text))
    codes = [b.code for b in boundaries]
    assert codes == ["AC-2", "AC-2(1)", "AC-3"]
    assert boundaries[1].level > boundaries[0].level  # AC-2(1) nests under AC-2


def test_standard_clause_ignores_table_of_contents_dot_leaders() -> None:
    text = "4  Context of the organization  ..................................... 12\n" "Real prose, no heading here.\n"
    boundaries = standard_clause.detect_boundaries(_lines(text))
    assert boundaries == []


def test_regulation_article_recognizes_arabic_structure() -> None:
    text = "الباب الأول\n" "الفصل الأول\n" "المادة الأولى: التعريفات: نص المادة هنا\n" "نص إضافي.\n" "المادة الثانية: تعريف الشركة:\n"
    boundaries = regulation_article.detect_boundaries(_lines(text))
    assert [b.level for b in boundaries] == [1, 2, 3, 3]
    assert boundaries[2].code == "الأولى"
    assert boundaries[2].title == "التعريفات: نص المادة هنا"


def test_regulation_article_recognizes_english_and_nca_ecc() -> None:
    text = "Chapter One: Definitions\n" "Article 1: Scope\n" "Body text.\n" "1-1-1 Establish a policy\n" "Body.\n"
    boundaries = regulation_article.detect_boundaries(_lines(text))
    codes = [b.code for b in boundaries]
    assert codes == ["Chapter One", "Article 1", "1-1-1"]


def test_contract_clause_recognizes_numbered_and_lettered_and_schedule() -> None:
    text = (
        "1. Definitions\n"
        "Body.\n"
        "1.1 Interpretation\n"
        "(a) first sub-clause text\n"
        "(b) second sub-clause text\n"
        "Schedule 1: Pricing\n"
        "Body.\n"
    )
    boundaries = contract_clause.detect_boundaries(_lines(text))
    codes = [b.code for b in boundaries]
    assert codes == ["1", "1.1", "(a)", "(b)", "Schedule 1"]
    assert boundaries[-1].level == 1  # Schedule is a top-level sibling, not nested under 1.1


def test_contract_defined_term_pattern_matches() -> None:
    assert contract_clause.DEFINED_TERM_PATTERN.search('"Confidential Information" means any data disclosed.')


def test_policy_procedure_all_caps_headings() -> None:
    text = "MESSAGE FROM THE CEO\n" "Some narrative text about the company.\n" "COMPLIANCE WITH LEGAL REQUIREMENTS\n" "More narrative.\n"
    boundaries = policy_procedure.detect_boundaries(_lines(text), mode="policy")
    titles = [b.title for b in boundaries]
    assert titles == ["MESSAGE FROM THE CEO", "COMPLIANCE WITH LEGAL REQUIREMENTS"]
    assert all(b.level == 1 for b in boundaries)


def test_policy_procedure_numbered_vocabulary_headings() -> None:
    text = "1. Purpose\n" "This policy exists to...\n" "2. Scope\n" "This applies to all staff.\n"
    boundaries = policy_procedure.detect_boundaries(_lines(text), mode="policy")
    assert [b.code for b in boundaries] == ["1", "2"]


def test_policy_procedure_step_mode() -> None:
    text = "Step 1: Submit the request\n" "Details.\n" "a) Attach supporting documents\n" "Step 2: Obtain approval\n" "Details.\n"
    boundaries = policy_procedure.detect_boundaries(_lines(text), mode="procedure")
    assert boundaries[0].level == 1
    assert boundaries[1].level == 2  # lettered sub-step nests under the preceding step
    assert boundaries[2].level == 1
