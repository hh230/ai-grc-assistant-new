"""Language: detection (Arabic / English / mixed) and language-aware policy + directive."""

from __future__ import annotations

from decision_engine import UserRequest
from pipeline_contracts import TenantContext
from prompt_orchestrator import Language, PromptOrchestrator, detect_language
from prompt_orchestrator.models import SegmentKind

from tests.conftest import make_context_package, make_plan

_TENANT = TenantContext(tenant_id="org_acme", principal_id="u1")


def test_detect_pure_english():
    assert detect_language("What does ISO 27001 require for access control?") == Language.ENGLISH


def test_detect_pure_arabic():
    assert detect_language("ما هي متطلبات ضبط الوصول في الأيزو؟") == Language.ARABIC


def test_detect_mixed():
    assert detect_language("قارن بين ISO 27001 و NIST CSF لضبط الوصول") == Language.MIXED


def test_detect_empty_defaults_english():
    assert detect_language("") == Language.ENGLISH
    assert detect_language("A.5.15") == Language.ENGLISH


def test_english_request_applies_english_policy_not_arabic():
    req = PromptOrchestrator().orchestrate(
        make_plan("lookup"), make_context_package(), UserRequest(tenant=_TENANT, query="access control policy"))
    ids = req.metrics.policies_applied
    assert any("english_policy" in p for p in ids)
    assert not any("arabic_policy" in p for p in ids)
    assert req.language == Language.ENGLISH


def test_arabic_request_applies_arabic_policy_and_directive():
    req = PromptOrchestrator().orchestrate(
        make_plan("lookup", language="ar"), make_context_package(),
        UserRequest(tenant=_TENANT, query="ما هي سياسة التحكم في الوصول المطلوبة؟"))
    assert req.language == Language.ARABIC
    assert any("arabic_policy" in p for p in req.metrics.policies_applied)
    # the Arabic answer directive is present in the system prompt
    assert "العربية" in req.segment(SegmentKind.IDENTITY).content


def test_mixed_request_applies_both_language_policies():
    req = PromptOrchestrator().orchestrate(
        make_plan("comparison"), make_context_package(),
        UserRequest(tenant=_TENANT, query="قارن بين ISO 27001 و NIST CSF"))
    ids = req.metrics.policies_applied
    assert req.language == Language.MIXED
    assert any("arabic_policy" in p for p in ids) and any("english_policy" in p for p in ids)


def test_explicit_language_override():
    req = PromptOrchestrator().orchestrate(
        make_plan("lookup"), make_context_package(), UserRequest(tenant=_TENANT, query="access control"),
        language=Language.ARABIC)
    assert req.language == Language.ARABIC
