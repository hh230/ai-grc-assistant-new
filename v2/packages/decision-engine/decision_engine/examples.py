"""A runnable demonstration: 30+ real GRC questions (Arabic and English) and the
DecisionPlan the engine produces for each. Run with `python -m decision_engine.examples`.
Illustration/verification only — not part of the engine."""

from __future__ import annotations

import json

from decision_engine import DecisionEngine, UserRequest
from pipeline_contracts import TenantContext

# Illustration only: a demo tenant so the examples build a valid request (ADR 0040 §4).
_DEMO_TENANT = TenantContext(tenant_id="demo_org", principal_id="demo_user")

EXAMPLES: list[tuple[str, bool]] = [
    # (query, has_document)
    ("What is ISO 27001 clause A.5.15?", False),
    ("Where does the PDPL define personal data?", False),
    ("Explain the risk treatment process in ISO 31000", False),
    ("Why is segregation of duties important?", False),
    ("Compare ISO 27001 with ECC", False),
    ("Compare ISO 27001 vs NIST CSF vs COBIT", False),
    ("Are we compliant with the PDPL?", False),
    ("Run a compliance review against SAMA CSF", False),
    ("Review our information security policy", False),
    ("Is this policy adequate for NCA ECC?", False),
    ("Extract the obligations from the Personal Data Protection Law", False),
    ("What obligations do we have under PDPL for data transfer?", False),
    ("Perform a risk analysis of our cloud migration", False),
    ("Assess the risks of third-party vendor onboarding", False),
    ("Do a gap assessment of our controls against NCA ECC", False),
    ("Which controls does our policy not cover?", False),
    ("Which ISO 27001 control addresses access management?", False),
    ("Map ISO 27001 to NIST CSF", False),
    ("Map the controls in ISO 27001 to NCA ECC", False),
    ("Summarize NIST SP 800-53", False),
    ("Summarize this document", True),
    ("Analyze this uploaded contract", True),
    ("Hello, what can you do?", False),
    ("Compare ISO 27001 with ECC and tell me which controls our policy does not cover", False),
    ("What is the weather today?", False),
    # Arabic
    ("قارن بين ISO 27001 و NIST CSF", False),
    ("ما هي متطلبات NCA ECC للتشفير", False),
    ("اشرح إطار إدارة المخاطر", False),
    ("هل هذه السياسة متوافقة مع نظام حماية البيانات الشخصية", False),
    ("استخرج الالتزامات من نظام حماية البيانات", False),
    ("حلل المخاطر التشغيلية لعملية الاستحواذ", False),
    ("ما هي الفجوات في ضوابطنا مقابل الضوابط الأساسية للأمن السيبراني", False),
    ("لخص هذا المستند", True),
    ("مرحبا، كيف يمكنك مساعدتي", False),
    ("ما هو الطقس اليوم", False),
]


def main() -> int:
    engine = DecisionEngine()
    header = f"{'#':>2}  {'QUERY':52s}  {'INTENT':22s} {'WF-PASS':7s} {'RRK':3s} {'GATE':4s} {'DOC':3s} {'MS':2s} {'BUD':3s} {'CONF':4s}  PROFILES"
    print(header)
    print("-" * len(header))
    for i, (query, has_doc) in enumerate(EXAMPLES, start=1):
        p = engine.decide(UserRequest(query=query, has_document=has_doc, tenant=_DEMO_TENANT))
        display = (query[:50] + "…") if len(query) > 51 else query
        print(
            f"{i:>2}  {display:52s}  {p.intent.value:22s} "
            f"{('R' if p.requires_retrieval else '-')}{p.retrieval_passes:<6d} "
            f"{'yes' if p.requires_reranker else ' - ':3s} "
            f"{'yes' if p.requires_human_gate else ' -  ':4s} "
            f"{'yes' if p.requires_document else ' - ':3s} "
            f"{'Y' if p.multi_step else '-':2s} "
            f"{p.context_budget:<3d} {p.confidence:<4.2f}  {','.join(p.target_profiles)}"
        )

    print("\n\n─── Full DecisionPlan JSON for two representative requests ───\n")
    for query, has_doc in [("Compare ISO 27001 with ECC", False),
                           ("Compare ISO 27001 with ECC and tell me which controls our policy does not cover", False)]:
        print(f"» {query}")
        print(json.dumps(engine.decide(UserRequest(query=query, has_document=has_doc, tenant=_DEMO_TENANT)).to_dict(), ensure_ascii=False, indent=2))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
