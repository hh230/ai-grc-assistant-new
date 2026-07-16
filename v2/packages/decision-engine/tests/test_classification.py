from __future__ import annotations

import pytest
from decision_engine import DecisionEngine, Intent, UserRequest
from pipeline_contracts import TenantContext

_TENANT = TenantContext(tenant_id="org_acme", principal_id="u1")

ENGINE = DecisionEngine()


def intent_of(query: str, has_document: bool = False) -> str:
    return ENGINE.decide(UserRequest(tenant=_TENANT, query=query, has_document=has_document)).intent


# ── every intent, English ─────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "query,expected",
    [
        ("What is ISO 27001 clause A.5.15?", Intent.LOOKUP),
        ("Explain risk management under ISO 31000", Intent.EXPLANATION),
        ("Compare ISO 27001 with ECC", Intent.COMPARISON),
        ("Are we compliant with PDPL?", Intent.COMPLIANCE_REVIEW),
        ("Review our information security policy", Intent.POLICY_REVIEW),
        ("Extract the obligations from the PDPL", Intent.OBLIGATION_EXTRACTION),
        ("Perform a risk analysis of our cloud migration", Intent.RISK_ANALYSIS),
        ("Do a gap assessment of our controls against NCA ECC", Intent.GAP_ASSESSMENT),
        ("Which controls in ISO 27001 address access management?", Intent.CONTROL_MAPPING),
        ("Map ISO 27001 to NIST CSF", Intent.CROSS_FRAMEWORK_MAPPING),
        ("Summarize NIST SP 800-53", Intent.SUMMARIZATION),
        ("Analyze this document", Intent.DOCUMENT_ANALYSIS),
        ("Hello, what can you do?", Intent.CONVERSATION),
    ],
)
def test_english_intents(query: str, expected: Intent) -> None:
    assert intent_of(query) == expected.value


# ── every intent, Arabic (incl. the spec's examples) ──────────────────────────
@pytest.mark.parametrize(
    "query,expected",
    [
        ("ما هي متطلبات NCA ECC", Intent.LOOKUP),
        ("اشرح إدارة المخاطر في ISO 31000", Intent.EXPLANATION),
        ("قارن بين ISO 27001 و NIST", Intent.COMPARISON),
        ("هل نحن ممتثلون لنظام حماية البيانات الشخصية", Intent.COMPLIANCE_REVIEW),
        ("هل هذه السياسة متوافقة مع المعايير", Intent.POLICY_REVIEW),
        ("استخرج الالتزامات من نظام حماية البيانات", Intent.OBLIGATION_EXTRACTION),
        ("حلل المخاطر التشغيلية", Intent.RISK_ANALYSIS),
        ("ما هي الفجوات في ضوابطنا مقابل الضوابط الأساسية", Intent.GAP_ASSESSMENT),
        ("لخص هذا المستند", Intent.SUMMARIZATION),
        ("مرحبا، ماذا تستطيع أن تفعل", Intent.CONVERSATION),
    ],
)
def test_arabic_intents(query: str, expected: Intent) -> None:
    assert intent_of(query) == expected.value


# ── the specific spec keyword → intent examples ───────────────────────────────
@pytest.mark.parametrize(
    "query,expected",
    [
        ("قارن ISO 27001 و ECC", Intent.COMPARISON),
        ("لخص التقرير", Intent.SUMMARIZATION),
        ("اشرح الحوكمة", Intent.EXPLANATION),
        ("هل هذه السياسة كافية", Intent.POLICY_REVIEW),
        ("ما هي ضوابط الأمن", Intent.LOOKUP),
        ("استخرج الالتزامات", Intent.OBLIGATION_EXTRACTION),
        ("حلل المخاطر", Intent.RISK_ANALYSIS),
    ],
)
def test_spec_keyword_examples(query: str, expected: Intent) -> None:
    assert intent_of(query) == expected.value


# ── ambiguous ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "query",
    [
        "ISO 27001 and our policy",  # GRC topic, no task verb
        "ISO 27001 و سياستنا",
        "NCA ECC controls",  # just an entity, no verb
    ],
)
def test_ambiguous_requests(query: str) -> None:
    plan = ENGINE.decide(UserRequest(tenant=_TENANT, query=query))
    assert plan.intent == Intent.AMBIGUOUS.value
    assert plan.requires_retrieval is False
    assert plan.confidence < 0.5
    assert "ambiguous" in plan.reason.lower()


# ── unsupported / out of scope ────────────────────────────────────────────────
@pytest.mark.parametrize(
    "query",
    [
        "What is the weather today?",
        "ما هو الطقس اليوم",
        "Tell me a joke",
        "",
        "   ",
    ],
)
def test_unsupported_requests(query: str) -> None:
    plan = ENGINE.decide(UserRequest(tenant=_TENANT, query=query))
    assert plan.intent == Intent.UNSUPPORTED.value
    assert plan.requires_retrieval is False


# ── conversation never retrieves ──────────────────────────────────────────────
@pytest.mark.parametrize("query", ["hi", "hello", "thanks", "شكرا", "من أنت"])
def test_conversation_never_retrieves(query: str) -> None:
    plan = ENGINE.decide(UserRequest(tenant=_TENANT, query=query))
    assert plan.intent == Intent.CONVERSATION.value
    assert plan.requires_retrieval is False
    assert plan.retrieval_passes == 0
    assert plan.context_budget == 0


def test_greeting_with_weak_grc_word_stays_conversation() -> None:
    # "how can you help" weakly hits explanation via "how", but the greeting must win
    assert intent_of("مرحبا، كيف يمكنك مساعدتي") == Intent.CONVERSATION.value
    assert intent_of("hi there, what can you do?") == Intent.CONVERSATION.value


def test_greeting_then_real_grc_verb_is_the_grc_intent() -> None:
    # a real GRC task verb outranks a leading greeting
    assert intent_of("hi, compare ISO 27001 with ECC") == Intent.COMPARISON.value
